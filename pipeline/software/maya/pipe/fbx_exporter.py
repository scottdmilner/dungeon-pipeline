'''
INSTRUCTIONS:
1. Select your character's "EXPORTSET_Unreal" selection set from the outliner (only 1 character)
2. Run this script (opens a UI)
3. Click which thing you want to export (TPose, Anim, or Both)
4. It will auto-export your desired FBX files to the same directory as your current Maya file
5. They will be titled...
"myCurrentMayaFileName_TPOSE.fbx"
"myCurrentMayaFileName_ANIM.fbx"

See instructions on discord for import of animations to Unreal

Note: This will only work on Windows (because that's all the FBXGameExporter supports)
'''
import maya.cmds as mc
import maya.mel as mel

character_options = ["Kitsune", "Ninja"]
destination_path = "G:\\shrineflow\\assets\\Animation"
character_destination_paths = {
    "Kitsune": "G:\\shrineflow\\assets\\Animation\\Kitsune",
    "Ninja": "G:\\shrineflow\\assets\\Animation\\Ninja",
}

def close_window(window_name):
    mc.deleteUI(window_name, window=True)

def run_ui():
    buttons = []
    texts_to_disable = []

    def enableButtons(*args):
        for button in buttons:
            mc.button(button, edit=True, enable=True)
        for text in texts_to_disable:
            mc.text(text, edit=True, enable=False)
            mc.text(text, edit=True, visible=False)

    window = mc.window("fbx_exporter", title="Unreal Rig Exporter")
    mc.columnLayout(adjustableColumn=True, rowSpacing=5)
    # Character select buttons
    character_select = mc.radioButtonGrp(label="Character", labelArray2=character_options, numberOfRadioButtons=2, onCommand=enableButtons, 
                                            columnAlign3=["left", "left", "left"], columnAttach3=["left", "left", "left"], columnOffset3=[2, 2, 2])

    def get_selected_character():
        selected = mc.radioButtonGrp(character_select, query=True, select=True)
        return character_options[selected - 1]

    def on_tpose(*args):
        export(get_selected_character(), tpose=True, anim=False)
        close_window(window)

    def on_anim(*args):
        export(get_selected_character(), tpose=False, anim=True)
        close_window(window)

    def on_both(*args):
        export(get_selected_character(), tpose=True, anim=True)
        close_window(window)

    def on_cancel(*args):
        mc.error('Export canceled by user')
        close_window(window)

    # confirm dialog
    mc.text('Which would you like to export?')
    warning = mc.text('Pick a character in order to enable export.', backgroundColor=[1, 0, 0])
    texts_to_disable.append(warning)
    mc.rowLayout(numberOfColumns=4, columnAttach4=["both", "both", "both", "both"])
    tpose_btn = mc.button(label='T Pose', enable=False, command=on_tpose)
    anim_btn = mc.button(label='Anim', enable=False, command=on_anim)
    both_btn = mc.button(label='Both', enable=False, command=on_both)
    cancel_btn = mc.button(label='Cancel', enable=False, command=on_cancel)
    buttons.extend([tpose_btn, anim_btn, both_btn, cancel_btn])
    mc.setParent("..")

    mc.showWindow(window)

def export(selected_character, tpose: bool = False, anim: bool = False):
    print("Export called on ", selected_character, " tpose: ", tpose, " anim: ", anim)
    if selected_character not in character_options:
        mc.error("Error selecting character: selected character ", selected_character, " not in options (", character_options, ")")
        return

    rigSet = mc.ls(sl=True)[0]
    # "ed:EXPORTSET_Unreal"
    # "letty:EXPORTSET_Unreal"
    # "vaughn:EXPORTSET_Unreal"

    timelineStart = mc.playbackOptions(min=True,q=True)
    timelineEnd = mc.playbackOptions(max=True,q=True)

    mc.loadPlugin( 'gameFbxExporter.mll' )

    origSel = mc.ls(sl=True)

    mc.select(rigSet)
    mel.eval('gameFbxExporter;')

    #switch to model tab
    mel.eval('gameExp_ChangeExportType(1);')
    mel.eval("gameExp_CurrentTabChanged();")
    mel.eval("gameExp_UpdatePrefix();")
    mel.eval("gameExp_PopulatePresetList();gameExp_CreateExportTypeUIComponents();")


    sceneNameLong = mc.file(q=True, sn=True, shn=True)
    sceneName = sceneNameLong.split('.')[0]
    scenePath = mc.file(q=True, sn=True).replace(sceneNameLong, '')

    #switch to 'export selection' mode
    mel.eval('''setAttr("gameExporterPreset1.exportSetIndex") `optionMenu -q -select model_gameExporterExportSet`; gameExp_CreateExportTypeUIComponents;''')

    #set the tpose export path
    mc.setAttr('gameExporterPreset1.exportFilename',sceneName + '_TPOSE',type='string')
    mc.setAttr('gameExporterPreset1.exportPath',character_destination_paths[selected_character],type='string')
    mc.setAttr('gameExporterPreset1.exportSetIndex',2)

    #switch to the "Animation Clips" tab
    mel.eval('gameExp_ChangeExportType(2);')
    mel.eval("gameExp_CurrentTabChanged();")

    #delete the current animation clip if one exists
    try:
        mel.eval("gameExp_DeleteAnimationClipLayout 0;")
    except:
        pass

    #set the animation export path
    mc.setAttr('gameExporterPreset2.exportFilename',sceneName + '',type='string')
    mc.setAttr('gameExporterPreset2.exportPath',character_destination_paths[selected_character],type='string')
    mc.setAttr('gameExporterPreset2.exportSetIndex',2)
    mc.setAttr('gameExporterPreset2.animClips[0].animClipName', '_ANIM', type='string' )

    #switch to "Model" tab and export animation
    mel.eval('gameExp_ChangeExportType(1);')
    mel.eval("gameExp_CurrentTabChanged();")
    mel.eval("gameExp_UpdatePrefix();")
    mel.eval("gameExp_PopulatePresetList();gameExp_CreateExportTypeUIComponents();")
    mc.setAttr("gameExporterPreset2.animClips[0].animClipStart",timelineStart)
    mc.setAttr("gameExporterPreset2.animClips[0].animClipEnd",timelineEnd)
    if tpose:
        mel.eval("gameExp_DoExport")

    #switch to "Animation Clips" tab and export animation
    mel.eval('gameExp_ChangeExportType(2);')
    mel.eval("gameExp_CurrentTabChanged();")
    mel.eval("gameExp_UpdatePrefix();")
    mel.eval("gameExp_PopulatePresetList();gameExp_CreateExportTypeUIComponents();")
    if anim:
        mc.select(hi=True)
        mel.eval("gameExp_DoExport")

    #Query which tab is active in the game exporter
    #tabLayout  -q -selectTabIndex "gameExporterTabLayout"
    #mel.eval("gameExp_AddNewAnimationClip 1;")
    #mel.eval("gameExp_SetUniqueAnimationClipName 0" + '''"_CLIP"''' + "gameExporterWindow|gameExporterTabFormLayout|gameExporterTabLayout|gameExporterAnimationTab|anim_gameExporterMainFormLayout|anim_gameExporterExportTypeFormLayout|formLayout433|anim_gameFbxExporterAnimClipFrameLayout|anim_gameFbxExporterAnimClipFormLayout|anim_gameFbxExporterScrollLayout|formLayout446|textField6;")

    mc.select(origSel)



def run_legacy():

    rigSet = mc.ls(sl=True)[0]
    # "ed:EXPORTSET_Unreal"
    # "letty:EXPORTSET_Unreal"
    # "vaughn:EXPORTSET_Unreal"

    ans = mc.confirmDialog(title = 'Unreal Rig Exporter', 
                        message = 'Which would you like to export?',
                        button = ['T Pose','Anim','Both','Cancel'])

    if ans == 'Cancel':
        mc.error('Export canceled by user')

    timelineStart = mc.playbackOptions(min=True,q=True)
    timelineEnd = mc.playbackOptions(max=True,q=True)

    mc.loadPlugin( 'gameFbxExporter.mll' )

    origSel = mc.ls(sl=True)

    mc.select(rigSet)
    mel.eval('gameFbxExporter;')

    #switch to model tab
    mel.eval('gameExp_ChangeExportType(1);')
    mel.eval("gameExp_CurrentTabChanged();")
    mel.eval("gameExp_UpdatePrefix();")
    mel.eval("gameExp_PopulatePresetList();gameExp_CreateExportTypeUIComponents();")


    sceneNameLong = mc.file(q=True, sn=True, shn=True)
    sceneName = sceneNameLong.split('.')[0]
    scenePath = mc.file(q=True, sn=True).replace(sceneNameLong, '')

    #switch to 'export selection' mode
    mel.eval('''setAttr("gameExporterPreset1.exportSetIndex") `optionMenu -q -select model_gameExporterExportSet`; gameExp_CreateExportTypeUIComponents;''')

    #set the tpose export path
    mc.setAttr('gameExporterPreset1.exportFilename',sceneName + '_TPOSE',type='string')
    mc.setAttr('gameExporterPreset1.exportPath',scenePath,type='string')
    mc.setAttr('gameExporterPreset1.exportSetIndex',2)

    #switch to the "Animation Clips" tab
    mel.eval('gameExp_ChangeExportType(2);')
    mel.eval("gameExp_CurrentTabChanged();")

    #delete the current animation clip if one exists
    try:
        mel.eval("gameExp_DeleteAnimationClipLayout 0;")
    except:
        pass

    #set the animation export path
    mc.setAttr('gameExporterPreset2.exportFilename',sceneName + '',type='string')
    mc.setAttr('gameExporterPreset2.exportPath',scenePath,type='string')
    mc.setAttr('gameExporterPreset2.exportSetIndex',2)
    mc.setAttr('gameExporterPreset2.animClips[0].animClipName', '_ANIM', type='string' )

    #switch to "Model" tab and export animation
    mel.eval('gameExp_ChangeExportType(1);')
    mel.eval("gameExp_CurrentTabChanged();")
    mel.eval("gameExp_UpdatePrefix();")
    mel.eval("gameExp_PopulatePresetList();gameExp_CreateExportTypeUIComponents();")
    mc.setAttr("gameExporterPreset2.animClips[0].animClipStart",timelineStart)
    mc.setAttr("gameExporterPreset2.animClips[0].animClipEnd",timelineEnd)
    if ans == 'Both' or ans == 'T Pose':
        mel.eval("gameExp_DoExport")

    #switch to "Animation Clips" tab and export animation
    mel.eval('gameExp_ChangeExportType(2);')
    mel.eval("gameExp_CurrentTabChanged();")
    mel.eval("gameExp_UpdatePrefix();")
    mel.eval("gameExp_PopulatePresetList();gameExp_CreateExportTypeUIComponents();")
    if ans == 'Both' or ans == 'Anim':
        mc.select(hi=True)
        mel.eval("gameExp_DoExport")

    #Query which tab is active in the game exporter
    #tabLayout  -q -selectTabIndex "gameExporterTabLayout"
    #mel.eval("gameExp_AddNewAnimationClip 1;")
    #mel.eval("gameExp_SetUniqueAnimationClipName 0" + '''"_CLIP"''' + "gameExporterWindow|gameExporterTabFormLayout|gameExporterTabLayout|gameExporterAnimationTab|anim_gameExporterMainFormLayout|anim_gameExporterExportTypeFormLayout|formLayout433|anim_gameFbxExporterAnimClipFrameLayout|anim_gameFbxExporterAnimClipFormLayout|anim_gameFbxExporterScrollLayout|formLayout446|textField6;")

    mc.select(origSel)