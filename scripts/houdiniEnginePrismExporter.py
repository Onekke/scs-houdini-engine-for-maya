import functools

import maya.mel as mel
import maya.cmds as cmds
import pymel.core as pm

from PySide2.QtCore import *
from PySide2.QtWidgets import *
from PySide2.QtGui import *

# Before doing anything, let's make sure our Prismtool plugin is loaded.
import shelfTool
shelfTool.ensurePrismtoolLoaded()

import constants
import qwidgetUtils
from core._checkType import checkType

# TODO - After new Vertex Color Mixer release - Refactor usage/encapsulation of the _QColorSetToolWidget.
import qwidgets._QColorSetToolWidget
from qwidgets._QColorSetToolWidget import _COLOR_SETS


_SUPPORTED_MODEL_TYPES = [
    # constants.MODEL_TYPE.model, # Not fully implemented. I need to see the json files describing the part/variant connections.
    constants.MODEL_TYPE.curve,
]


_SUBPART_TRANSLATION_DICT = {
    "vis"    : "visual",
    "shadow" : "shadow",
    "coll"   : "collision",
    "terr"   : "terrain1",
}


_EXPORTER_NAME_BY_LOD_NAME = {
    "lod0": "_",
    "lod_bake": "_lod1",
}


def _assignMaterial(meshPath, materialName):
    cmds.select(meshPath)
    cmds.hyperShade(assign=materialName)
    cmds.select(clear=True)


class _QImportedTypeSelectionDialog(QDialog):
    def __init__(self):
        super().__init__(qwidgetUtils.getMayaMainWindow())

        self.setWindowTitle("Select Model Type")
        self.setWindowFlags(Qt.Dialog)
        self.setAttribute(Qt.WA_DeleteOnClose)

        self._selectedModelType = None

        self._layout = QVBoxLayout(self)

        buttonsLayout = QHBoxLayout()
        for modelType in _SUPPORTED_MODEL_TYPES:
            button = QPushButton(modelType.name)
            if modelType == constants.MODEL_TYPE.model:
                button.setDefault(True)
            button.clicked.connect(functools.partial(self._onModelTypeSelected, modelType))
            buttonsLayout.addWidget(button)

        self._layout.addWidget(QLabel("Select model type to import:"))
        self._layout.addLayout(buttonsLayout)


    def _onModelTypeSelected(self, modelType):
        checkType(modelType, constants.MODEL_TYPE)

        self._selectedModelType = modelType
        self.accept()


    def getSelectedModelType(self):
        return self._selectedModelType


class _RockImporter:
    def __init__(self, modelType):
        checkType(modelType, constants.MODEL_TYPE)
        assert(modelType in _SUPPORTED_MODEL_TYPES)

        self._modelType = modelType
        self._targetMeshes = pm.ls(type=pm.nt.Mesh) # All meshes in the scene.
        self._targetTransforms = [n.getParent() for n in self._targetMeshes]

        print("Target meshes: {}".format(self._targetMeshes))
        print("Target transforms: {}".format(self._targetTransforms))


    def _initVertexColors(self):
        print("| Initializing vertex colors...")
        pm.select(self._targetTransforms)

        colorSetNames = ["color", "decal", "ao", "ao2", "colorSet1"]

        colorSets = cmds.polyColorSet(q=True, allColorSets=True)

        if "Cd" in colorSets:
            print("|  | Found 'Cd', setting vtx colors from imported houdini mesh.")
            cmds.polyColorSet(copy=True, colorSet="Cd", newColorSet="color", representation="RGB")
            cmds.polyColorSet(copy=True, colorSet="Cd", newColorSet="decal", representation="RGBA")
            cmds.polyColorSet(delete=True, colorSet="Cd")
            cmds.polyColorSet(create=True, clamped=1, representation="RGB", colorSet="ao")
            cmds.polyColorPerVertex(rgb=(0.5, 0.5, 0.5))
            cmds.polyColorSet(create=True, clamped=1, representation="RGB", colorSet="ao2")
            cmds.polyColorPerVertex(rgb=(0.5, 0.5, 0.5))
            cmds.polyColorSet(create=True, clamped=1, representation="RGBA", colorSet="colorSet1")
            cmds.polyColorPerVertex(rgb=(0.5, 0.5, 0.5))
            pm.PrismColor(bakeVertexColors=True)
        else:
            print("|  | Couldn't find 'Cd', vtx color set to default values.")
            for colorSetName in colorSetNames:
                colorSetDef = _COLOR_SETS[colorSetName]
                qwidgets._QColorSetToolWidget._createColorSetIfMissing(colorSetDef, self._targetMeshes)

        pm.delete(all=True, constructionHistory=True)


    def _initHierarchy(self):
        print("Initializing the hierarchy...")

        # Ensure a PrismExportTool exists.
        exportTools = pm.ls("|PrismExport|PrismExportShape", type=pm.nt.PrismExportTool)
        if len(exportTools) == 0:
            mel.eval("PrismCreateExporterTool;")

        # prismMaterialSystemNodes = pm.ls(type=pm.nt.PrismMaterial)
        # cgfxShaderNodes = pm.ls(type=pm.nt.CgfxShader)
        # assert (not (len(prismMaterialSystemNodes) > 0 and len(cgfxShaderNodes) > 0))
        # shaderNodes = prismMaterialSystemNodes + cgfxShaderNodes
        # shaderNames = [n.nodeName() for n in shaderNodes]

        # shadowShaderNode = None
        # collShaderNode = None
        # bakedLodShaderNode = None

        createdExporters = []

        # for shaderNode in shaderNodes:
        #     if isinstance(shaderNode, pm.nt.CgfxShader):
        #         cgfxName = shaderNode.getCgfxName()
        #         if cgfxName == "eut2.shadowonly":
        #             shadowShaderNode = shaderNode
        #         elif cgfxName == "eut2.none":
        #             collShaderNode = shaderNode
        #         elif cgfxName == "eut2.baked":
        #             bakedLodShaderNode = shaderNode

        #     elif isinstance(shaderNode, pm.nt.PrismMaterial):
        #         if shaderNode.isBakedMaterial():
        #             bakedLodShaderNode = shaderNode
        #             continue

        #         uniqueNonDefaultAutoMats = shaderNode.getAllUniquePrismAutoMats(includeDefault=False)
        #         if len(uniqueNonDefaultAutoMats) == 0:
        #             defaultAutoMat = shaderNode.getDefaultPrismAutoMat()
        #             umatUfsPath = defaultAutoMat.umatUfsPath.get()
        #             if umatUfsPath == "/umatlib/special/collision_umat.umat":
        #                 collShaderNode = shaderNode
        #             elif umatUfsPath == "/umatlib/special/shadow_caster_umat.umat":
        #                 shadowShaderNode = shaderNode

        #     else:
        #         assert False

        for transform in self._targetTransforms:
            transformName = transform.nodeName()
            pathComponents = transformName.split('__')

            assert(len(pathComponents) >= 4)

            targetPartName = pathComponents[0]
            targetSubpartName = pathComponents[1]
            targetLodName = pathComponents[2].lower()
            targetMaterialName = pathComponents[3]
            assert(targetLodName in _EXPORTER_NAME_BY_LOD_NAME)
            targetExporterName = _EXPORTER_NAME_BY_LOD_NAME[targetLodName]

            if not cmds.objExists(targetExporterName):
                prismExporter = pm.createNode(pm.nt.PrismExporter, name=targetExporterName)
                prismExporter.modelExportEnabled.set(True)
                prismExporter.modelType.set(self._modelType)
                createdExporters.append(prismExporter)
            else:
                prismExporter = pm.ls(targetExporterName, type=pm.nt.PrismExporter)[0]

            targetPartPath = "{}|{}".format(targetExporterName, targetPartName)
            if not cmds.objExists(targetPartPath):
                prismPart = pm.createNode(pm.nt.PrismPart2, name=targetPartName, parent=prismExporter)
            else:
                prismPart = pm.ls(targetPartPath, type=pm.nt.PrismPart2)[0]

            meshTransformParent = prismPart
            for subpartInfix, subpartName in _SUBPART_TRANSLATION_DICT.items():
                if subpartInfix == targetSubpartName:
                    targetSubpartPath = "{}|{}".format(targetPartPath, subpartName)
                    if not cmds.objExists(targetSubpartPath):
                        subpartNode = pm.createNode(pm.nt.PrismSubpart, name=subpartName, parent=prismPart)
                    meshTransformParent = subpartNode
            pm.parent(transform, meshTransformParent)

            meshPath = transform.getShape().fullPathName()

            # if targetMaterialName in shaderNames:
            #     _assignMaterial(meshPath, targetMaterialName)
            # elif targetMaterialName == "M_shadow" and shadowShaderNode is not None:
            #     _assignMaterial(meshPath, shadowShaderNode.nodeName())
            # elif targetMaterialName == "M_coll" and collShaderNode is not None:
            #     _assignMaterial(meshPath, collShaderNode.nodeName())

            # # In the original script, this overrides any material naming,
            # # let's keep it that way even though it is quite confusing.
            # if "shadow" in pathComponents and shadowShaderNode is not None:
            #     _assignMaterial(meshPath, shadowShaderNode.nodeName())
            # if "coll" in pathComponents and collShaderNode is not None:
            #     _assignMaterial(meshPath, collShaderNode.nodeName())
            # if "vis" in pathComponents and "LOD_bake" in pathComponents and bakedLodShaderNode is not None:
            #     _assignMaterial(meshPath, bakedLodShaderNode.nodeName())

        # Create PrismVariants...
        for exporter in createdExporters:
            prismVariant = pm.createNode(pm.nt.PrismVariant, name="Default", parent=exporter)

            # Note that Curves technically do not need any PrismVariants, however it is required
            # by our checks/conversion tools (removing this would be unnecesarilly complicated).
            # To adhere to the checks, we just need to create a Default PrismVariant and assign
            # it any PrismPart2. I.e. this is just a formality and has no consequence on the exported data.

            # Get any first part we find under the exporter.
            exporterParts = exporter.listRelatives(type=pm.nt.PrismPart2)
            assert(len(exporterParts) > 0)

            exporter.setPartVariantConnection(exporterParts[0].nodeName(), prismVariant.nodeName(), True)


    def run(self):
        print("Running the importer...")
        # (self._initVertexColors, "Initializing vertex colors...")
        _TASKS = [
            (self._initHierarchy, "Initializing the node hierarchy..."),
        ]

        progressDialog = QProgressDialog(minimum=0, maximum=len(_TASKS))
        progressDialog.setWindowTitle("Prism checks in progress...")
        progressDialog.setWindowModality(Qt.ApplicationModal)
        progressDialog.setLabelText("Preparing data.")
        progressDialog.setFixedWidth(300)
        progressDialog.forceShow()

        for callback, desc in _TASKS:
            progressDialog.setLabelText(desc)
            callback()
            progressDialog.setValue(progressDialog.value() + 1)

        progressDialog.close()


def create_node_hierarchy():
    if len(pm.ls(type=pm.nt.PrismExporter)) > 0:
        QMessageBox.critical(None, "PrismExporters Present", "There are PrismExporters already in the scene!")
        return

    prismMaterialSystemNodes = pm.ls(type=(pm.nt.PrismMaterial, pm.nt.PrismAutoMat))
    cgfxShaderNodes = pm.ls(type=pm.nt.CgfxShader)

    if len(prismMaterialSystemNodes) > 0 and len(cgfxShaderNodes) > 0:
        QMessageBox.critical(None, "Mixed Material Systems", "Cannot use both PrismMaterial system and Cgfx shader system at the same time!")
        return

    '''
    dialog = _QImportedTypeSelectionDialog()
    res = dialog.exec_()
    if not res:
        return
    modelType = dialog.getSelectedModelType()
    '''
    modelType = constants.MODEL_TYPE.curve

    rockImporter = _RockImporter(modelType)
    rockImporter.run()


if __name__ == "__main__":
    create_node_hierarchy()