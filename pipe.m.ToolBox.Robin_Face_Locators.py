# Building the Face
# Locators
import maya.cmds as cmds

cmds.group(em=True, name="Locators")

def create_locator(name, x, y, z):
    locator = cmds.spaceLocator(name=name)[0]
    cmds.move(x, y, z, locator)
create_locator("skull_bind_LOC", 0.0, 148.946, -1.415)
cmds.parent("skull_bind_LOC", "Locators")

create_locator("face_upper_bind_LOC", 0.0, 148.535, -0.646)
cmds.parent("face_upper_bind_LOC", "Locators")

create_locator("head_tip_bind_LOC", 0.0, 156.237, 0.066)
cmds.parent("head_tip_bind_LOC", "Locators")

create_locator("brow_inner_l_bind_LOC", 1.9224777221679688, 157.234375, 7.205977439880371)
cmds.parent("brow_inner_l_bind_LOC", "Locators")

create_locator("brow_main_l_bind_LOC", 4.198387145996094, 157.55564880371094, 6.387408256530762)
cmds.parent("brow_main_l_bind_LOC", "Locators")

create_locator("brow_peak_l_bind_LOC", 5.9982452392578125, 157.51654052734375, 5.1865129470825195)
cmds.parent("brow_peak_l_bind_LOC", "Locators")

create_locator("brow_inner_r_bind_LOC", -1.9220428466796875, 157.23423767089844, 7.206364631652832)
cmds.parent("brow_inner_r_bind_LOC", "Locators")

create_locator("brow_main_r_bind_LOC", -4.19866943359375, 157.55499267578125, 6.387154579162598)
cmds.parent("brow_main_r_bind_LOC", "Locators")

create_locator("brow_peak_r_bind_LOC", -5.997783660888672, 157.51683044433594, 5.186444282531738)
cmds.parent("brow_peak_r_bind_LOC", "Locators")

create_locator("eyeSocket_r_bind_LOC", -3.5427756309509277, 155.02047729492188, 3.995751142501831)
cmds.parent("eyeSocket_r_bind_LOC", "Locators")

create_locator("eye_r_bind_LOC", -3.5427756309509277, 155.02047729492188, 3.995751142501831)
cmds.parent("eye_r_bind_LOC", "Locators")

create_locator("iris_r_bind_LOC", -3.6470484733581543, 155.0205078125, 6.058708667755127)
cmds.parent("iris_r_bind_LOC", "Locators")

create_locator("pupil_r_bind_LOC", -3.6470484733581543, 155.0205078125, 6.058708667755127)
cmds.parent("pupil_r_bind_LOC", "Locators")

create_locator("eyeSocket_l_bind_LOC", 3.5432958602905273, 155.02047729492188, 3.995751142501831)
cmds.parent("eyeSocket_l_bind_LOC", "Locators")

create_locator("eye_l_bind_LOC", 3.5432958602905273, 155.02047729492188, 3.995751142501831)
cmds.parent("eye_l_bind_LOC", "Locators")

create_locator("iris_l_bind_LOC", 3.647508382797241, 155.0205078125, 6.058708667755127)
cmds.parent("iris_l_bind_LOC", "Locators")

create_locator("pupil_l_bind_LOC", 3.647508382797241, 155.0205078125, 6.058708667755127)
cmds.parent("pupil_l_bind_LOC", "Locators")

create_locator("face_lower_bind_LOC", 0.0, 154.289, -0.867)
cmds.parent("face_lower_bind_LOC", "Locators")

create_locator("face_mid_bind_LOC", 0.0, 147.761, -0.203)
cmds.parent("face_mid_bind_LOC", "Locators")

create_locator("nose_bridge_bind_LOC", -0.009210817838884111, 154.20272247612098, 6.868255446299961)
cmds.parent("nose_bridge_bind_LOC", "Locators")

create_locator("nose_bind_LOC", 0.0, 151.722, 8.582801822476329)
cmds.parent("nose_bind_LOC", "Locators")

create_locator("jaw_bind_LOC", 0.0, 150.539, -4.177)
cmds.parent("jaw_bind_LOC", "Locators")

create_locator("jaw_end_bind_LOC", 7.62939453125e-06, 145.11997985839844, 6.618426322937012)
cmds.parent("jaw_end_bind_LOC", "Locators")

create_locator("nose_l_nostril_bind_LOC", 0.495, 150.669, 8.234)
cmds.parent("nose_l_nostril_bind_LOC", "Locators")

create_locator("nose_r_nostril_bind_LOC", -0.495, 150.669, 8.234)
cmds.parent("nose_r_nostril_bind_LOC", "Locators")

create_locator("nose_bottom_bind_LOC", 0.0, 150.425, 8.533)
cmds.parent("nose_bottom_bind_LOC", "Locators")

create_locator("nose_l_outer_nostril_bind_LOC", 1.4512917205083236, 150.84691022800172, 7.997041809860042)
cmds.parent("nose_l_outer_nostril_bind_LOC", "Locators")

create_locator("nose_r_outer_nostril_bind_LOC", -1.451, 150.847, 7.997)
cmds.parent("nose_r_outer_nostril_bind_LOC", "Locators")

