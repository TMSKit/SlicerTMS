import os
import vtk, qt, ctk, slicer
from slicer.ScriptedLoadableModule import *
# from slicerserver import Server
# import nibabel as nib
import numpy as np
# from subprocess import check_output
import subprocess

import Mapper as M
import SlicerTMS as S


class Loader:

    def __init__(self, data_directory):

        self.data_directory = data_directory
        self._graymatter_file = 'gm.stl'
        self._fiber_file = 'fibers.vtk'
        self._coil_file = 'coil.stl'
        self._coil_scale = 3
        self._skin_file = 'skin.stl'
        self._magnorm_file = 'magnorm.nii.gz'
        self._magfield_file = 'magfield.nii.gz'
        self._conductivity_file = 'conductivity.nii.gz'

        self.modelNode = None
        self.fiberNode = None
        self.coilNode = None
        self.skinNode = None
        self.markupsPlaneNode = None

        self.conductivityNode = None
        self.magfieldGTNode = None
        self.magfieldNode = None
        self.magnormNode = None
        self.efieldNode = None
        self.enormNode = None
        self.coilDefaultMatrix = vtk.vtkMatrix4x4()

        self.IGTLNode = None

        self.showMag = False #switch between magnetic and electric field for visualization

    def callMapper(self, param1=None, param2=None):
        '''
        '''
        M.Mapper.map(self)

    def showFibers(self):
        fiberNode = slicer.util.getNode('fibers')
        modelNode = slicer.util.getNode('gm')
        if self == 2:
            print("Show Fibers")
            fiberNode.SetDisplayVisibility(1)
            modelNode.SetDisplayVisibility(0)
        elif self == 0:
            print("Show Brain Surface")
            fiberNode.SetDisplayVisibility(0)
            modelNode.SetDisplayVisibility(1)


    def newImage(self, caller, event):
        print('New CNN Image received via PyIgtl')
        M.Mapper.modifyIncomingImage(self)


    @staticmethod
    def loadExample(self, example_path):

        print('Your selected Example: ' + example_path)
        data_directory = os.path.join(os.path.dirname(slicer.modules.slicertms.path), '../', example_path)

        loader = Loader(data_directory)

        slicer.mrmlScene.Clear()

        #
        # 1. Brain:
        #
        brainModelFile = os.path.join( loader.data_directory, loader._graymatter_file )
        loader.modelNode = slicer.modules.models.logic().AddModel(brainModelFile,
                                                                slicer.vtkMRMLStorageNode.CoordinateSystemRAS)
        
        #
        # 2. Fibers:
        #

        fiberModelFile = os.path.join( loader.data_directory, loader._fiber_file )
        loader.fiberNode = slicer.modules.models.logic().AddModel(fiberModelFile,
                                                                slicer.vtkMRMLStorageNode.CoordinateSystemRAS)
        loader.fiberNode.SetDisplayVisibility(0)

        #
        # 3. Skin model:
        #
        skin = os.path.join( loader.data_directory, loader._skin_file )
        loader.skinNode = slicer.modules.models.logic().AddModel(skin, slicer.vtkMRMLStorageNode.CoordinateSystemRAS)
        skinDisplayNode = loader.skinNode.GetDisplayNode()
        skinDisplayNode.SetOpacity(0.3)


        #
        # 4. TMS coil:
        #
        coil = os.path.join( loader.data_directory, loader._coil_file )
        
        loader.coilNode = slicer.modules.models.logic().AddModel(coil, slicer.vtkMRMLStorageNode.CoordinateSystemRAS)
        
        # Set transform on the coil and resize it:
        parentTransform = vtk.vtkTransform()
        parentTransform.Scale(loader._coil_scale, loader._coil_scale, loader._coil_scale)
        
        loader.coilNode.ApplyTransformMatrix(parentTransform.GetMatrix())

        # Add a plane to the scene
        markupsPlaneNode = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLMarkupsPlaneNode', 'Coil')
        markupsPlaneNode.SetOrigin([0, 0, 110])
        markupsPlaneNode.SetNormalWorld([0, 0, -10])
        markupsPlaneNode.SetAxes([.5, 0, 0], [0, .5, 0], [0, 0, .5])
        markupsPlaneNode.SetAxes([.5, 0, 0], [0, .5, 0], [0, 0, .5])
        markupsPlaneNode.GetMarkupsDisplayNode().SetHandlesInteractive(True)
        markupsPlaneNode.GetMarkupsDisplayNode().SetRotationHandleVisibility(1)
        markupsPlaneNode.GetMarkupsDisplayNode().SetTranslationHandleVisibility(1)
        markupsPlaneNode.GetDisplayNode().SetSnapMode(slicer.vtkMRMLMarkupsDisplayNode.SnapModeToVisibleSurface)
        markupsPlaneNode.SetDisplayVisibility(1)
        
        loader.markupsPlaneNode = markupsPlaneNode

        loader.transformNode = slicer.mrmlScene.AddNode(slicer.vtkMRMLLinearTransformNode())
        loader.coilNode.SetAndObserveTransformNodeID(loader.transformNode.GetID())
        

        #
        # 5. Other stuff
        #

        # load magnorm (used for tesing and visualization, not useful for predicting E-field)
        loader.magnormNode = slicer.util.loadVolume( os.path.join( loader.data_directory, loader._magnorm_file ) )
        loader.magnormNode.SetName('MagNorm')
        loader.magnormNode.GetIJKToRASMatrix(loader.coilDefaultMatrix)


        # load magvector as a GridTransformNode 
        # the grid transform node (GTNode) only provides the 4D vtkImageData in the original space
        loader.magfieldGTNode  = slicer.util.loadTransform(os.path.join( loader.data_directory, loader._magfield_file ))

        # load conductivity
        loader.conductivityNode = slicer.util.loadVolume( os.path.join( loader.data_directory, loader._conductivity_file ) )
        

        # creat magfield vector volumeNode for visualizing rotated RBG-coded magnetic vector field
        loader.magfieldNode = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLVectorVolumeNode')
        loader.magfieldNode.SetSpacing(loader.conductivityNode.GetSpacing())
        loader.magfieldNode.SetOrigin(loader.conductivityNode.GetOrigin())
        loader.magfieldNode.SetName('MagVec')

        # create nodes for received E-field data from pyigtl 
        loader.efieldNode = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLVectorVolumeNode')
        loader.efieldNode.Copy(loader.magfieldNode)
        loader.efieldNode.SetName('EVec')

        loader.enormNode = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLScalarVolumeNode')
        loader.enormNode.Copy(loader.conductivityNode)
        loader.enormNode.SetName('ENorm')


        # IGTL connections
        loader.IGTLNode = slicer.vtkMRMLIGTLConnectorNode()
        slicer.mrmlScene.AddNode(loader.IGTLNode)
        # node should be visible in OpenIGTLinkIF module under connectors
        loader.IGTLNode.SetName('Connector1')
        # add command line stuff here
        loader.IGTLNode.SetTypeClient('localhost', 18944)
        # this will activate the the status of the connection:
        loader.IGTLNode.Start()
        loader.IGTLNode.RegisterIncomingMRMLNode(loader.efieldNode)
        loader.IGTLNode.RegisterOutgoingMRMLNode(loader.magfieldNode)
        loader.IGTLNode.PushOnConnect()
        print('OpenIGTLink Connector created! \n Check IGT > OpenIGTLinkIF and start external pyigtl server.')

        # observer for the icoming IGTL image data
        loader.pyigtlNode = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLVectorVolumeNode', 'pyigtl_data')
        observationTag = loader.pyigtlNode.AddObserver(slicer.vtkMRMLVectorVolumeNode.ImageDataModifiedEvent, loader.newImage)

        # # call one time
        loader.callMapper()

        # # interaction hookup
        loader.markupsPlaneNode.AddObserver(slicer.vtkMRMLMarkupsNode.PointModifiedEvent, loader.callMapper)

        #slicer.mrmlScene.AddObserver(slicer.vtkMRMLScene.NodeAddedEvent, loader.onNodeRcvd)

        return loader