# Copyright (c) 2022-2024, The Isaac Lab Project Developers.
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

import math

import omni.isaac.lab.sim as sim_utils
from omni.isaac.lab.assets import ArticulationCfg, AssetBaseCfg
from omni.isaac.lab.envs import ManagerBasedRLEnvCfg
from omni.isaac.lab.managers import EventTermCfg as EventTerm
from omni.isaac.lab.managers import ObservationGroupCfg as ObsGroup
from omni.isaac.lab.managers import ObservationTermCfg as ObsTerm
from omni.isaac.lab.managers import RewardTermCfg as RewTerm
from omni.isaac.lab.managers import SceneEntityCfg
from omni.isaac.lab.managers import TerminationTermCfg as DoneTerm
from omni.isaac.lab.scene import InteractiveSceneCfg
from omni.isaac.lab.utils import configclass

import omni.isaac.lab_tasks.manager_based.classic.cartpole.mdp as mdp

##
# Pre-defined configs
##
from omni.isaac.lab_assets.cartpole_double import CARTPOLE_CFG  # isort:skip


##
# Scene definition
##
#import omni.replicator.core as rep
from omni.isaac.lab.sensors.camera import Camera, CameraCfg
import omni.isaac.core.utils.prims as prim_utils


def create_camera():
    """Defines the camera sensor to add to the scene."""

    # Setup camera sensor
    # In contrast to the ray-cast camera, we spawn the prim at these locations.
    # This means the camera sensor will be attached to these prims.
    prim_utils.create_prim("/World/Origin_00", "Xform")
    prim_utils.create_prim("/World/Origin_01", "Xform")
    camera_cfg = CameraCfg(
        prim_path="/World/Origin_.*/CameraSensor",
        update_period=0,
        height=480,
        width=640,
        data_types=[
            "rgb"
        ],
        colorize_semantic_segmentation=False,
        colorize_instance_id_segmentation=False,
        colorize_instance_segmentation=False,
        spawn=sim_utils.PinholeCameraCfg(
            focal_length=24.0, focus_distance=400.0, horizontal_aperture=20.955, clipping_range=(0.1, 1.0e5)
        ),
    )

    # Create camera
    camera = Camera(cfg=camera_cfg)

    return camera


@configclass
class CartpoleDoubleSceneCfg(InteractiveSceneCfg):
    """Configuration for a cart-pole scene."""

    # cartpole
    robot: ArticulationCfg = CARTPOLE_CFG.replace(prim_path="{ENV_REGEX_NS}/Robot")

    # lights
    dome_light = AssetBaseCfg(
        prim_path="/World/DomeLight",
        spawn=sim_utils.DomeLightCfg(color=(0.9, 0.9, 0.9), intensity=500.0),
    )
    distant_light = AssetBaseCfg(
        prim_path="/World/DistantLight",
        spawn=sim_utils.DistantLightCfg(color=(0.9, 0.9, 0.9), intensity=2500.0),
        init_state=AssetBaseCfg.InitialStateCfg(rot=(0.738, 0.477, 0.477, 0.0)),
    )

    """lol = CameraCfg(
        prim_path="/Recording/Camera",
        update_period=0,
        height=480,
        width=640,
        data_types=[
            "rgb",
        ],
        colorize_semantic_segmentation=False,
        colorize_instance_id_segmentation=False,
        colorize_instance_segmentation=False,
        offset=CameraCfg.OffsetCfg(pos=(0.0, 0.0, 0.0)),
        spawn=sim_utils.PinholeCameraCfg(
            focal_length=24.0, focus_distance=400.0, horizontal_aperture=20.955, clipping_range=(0.1, 1.0e5)
        )
    )"""

##
# MDP settings
##


@configclass
class CommandsCfg:
    """Command terms for the MDP."""

    # no commands for this MDP
    null = mdp.NullCommandCfg()


@configclass
class ActionsCfg:
    """Action specifications for the MDP."""

    joint_effort = mdp.JointEffortActionCfg(asset_name="robot", joint_names=["RailToCart"], scale=10.0)


@configclass
class ObservationsCfg:
    """Observation specifications for the MDP."""

    @configclass
    class PolicyCfg(ObsGroup):
        """Observations for policy group."""

        # observation terms (order preserved)
        joint_pos_rel = ObsTerm(func=mdp.joint_pos_rel)
        joint_vel_rel = ObsTerm(func=mdp.joint_vel_rel)

        def __post_init__(self) -> None:
            self.enable_corruption = False
            self.concatenate_terms = True

    # observation groups
    policy: PolicyCfg = PolicyCfg()


@configclass
class EventCfg:
    """Configuration for events."""
    reset_to_default = EventTerm(
        func=mdp.reset_joints_to_default,
        mode="reset",
        params={
            "asset_cfg": SceneEntityCfg("robot"),
        },
    )

    # reset
    """reset_cart_position = EventTerm(
        func=mdp.reset_joints_by_offset,
        mode="reset",
        params={
            "asset_cfg": SceneEntityCfg("robot", joint_names=["RailToCart"]),
            "position_range": (-1.0, 1.0),
            "velocity_range": (-0.5, 0.5),
        },
    )"""

    reset_pole_position = EventTerm(
        func=mdp.reset_joints_by_offset,
        mode="reset",
        params={
            "asset_cfg": SceneEntityCfg("robot", joint_names=["CartToPole"]),
            #"position_range": (-math.pi * 0.25, math.pi * 0.25),
            #"position_range": (-math.pi, math.pi),
            "position_range": (math.pi, math.pi),
            #"position_range": (0.0, 0.0),
            "velocity_range": (0.0, 0.0),
        },
    )

    reset_pole_double_position = EventTerm(
        func=mdp.reset_joints_by_offset,
        mode="reset",
        params={
            "asset_cfg": SceneEntityCfg("robot", joint_names=["PoleToDouble"]),
            #"position_range": (-math.pi * 0.25, math.pi * 0.25),
            #"position_range": (math.pi / 2, math.pi / 2),
            "position_range": (0.0, 0.0),
            "velocity_range": (0.0, 0.0),
        },
    )


@configclass
class RewardsCfg:
    """Reward terms for the MDP."""

    # (1) Constant running reward
    alive = RewTerm(func=mdp.is_alive, weight=250.0)
    # (2) Failure penalty
    terminating = RewTerm(func=mdp.is_terminated, weight=-800.0)
    # (3) Primary task: keep pole upright
    pole_pos = RewTerm(
        func=mdp.joint_pos_target_l2,
        weight=-30.0,
        params={"asset_cfg": SceneEntityCfg("robot", joint_names=["CartToPole"]), "target": 0.0},
    )
    pole_pos_double = RewTerm(
        func=mdp.joint_pos_target_l2,
        weight=-30.0,
        params={"asset_cfg": SceneEntityCfg("robot", joint_names=["PoleToDouble"]), "target": 0.0},
    )
    # (4) Shaping tasks: lower cart velocity
    cart_vel = RewTerm(
        func=mdp.joint_vel_l1,
        weight=-10.0,
        params={"asset_cfg": SceneEntityCfg("robot", joint_names=["RailToCart"])},
    )
    # (5) Shaping tasks: lower pole angular velocity
    pole_vel = RewTerm(
        func=mdp.joint_vel_l1,
        weight=-10.0,
        params={"asset_cfg": SceneEntityCfg("robot", joint_names=["CartToPole"])},
    )
    # (6) Shaping tasks: center cart
    cart_pos = RewTerm(
        func=mdp.joint_pos_target_l2,
        weight=-5.0,
        params={"asset_cfg": SceneEntityCfg("robot", joint_names=["RailToCart"]), "target": 0.0},
    )


@configclass
class TerminationsCfg:
    """Termination terms for the MDP."""

    # (1) Time out
    time_out = DoneTerm(func=mdp.time_out, time_out=True)
    # (2) Cart out of bounds
    cart_out_of_bounds = DoneTerm(
        func=mdp.joint_pos_out_of_manual_limit,
        params={"asset_cfg": SceneEntityCfg("robot", joint_names=["RailToCart"]), "bounds": (-1.24, 1.24)},
    )


@configclass
class CurriculumCfg:
    """Configuration for the curriculum."""

    pass


##
# Environment configuration
##


@configclass
class CartpoleDoubleEnvCfg(ManagerBasedRLEnvCfg):
    """Configuration for the locomotion velocity-tracking environment."""

    # Scene settings
    scene: CartpoleDoubleSceneCfg = CartpoleDoubleSceneCfg(num_envs=4096, env_spacing=2.8)
    # Basic settings
    observations: ObservationsCfg = ObservationsCfg()
    actions: ActionsCfg = ActionsCfg()
    events: EventCfg = EventCfg()
    # MDP settings
    curriculum: CurriculumCfg = CurriculumCfg()
    rewards: RewardsCfg = RewardsCfg()
    terminations: TerminationsCfg = TerminationsCfg()
    # No command generator
    commands: CommandsCfg = CommandsCfg()

    # Post initialization
    def __post_init__(self) -> None:
        """Post initialization."""
        # general settings
        self.decimation = 1
        self.episode_length_s = 10
        # viewer settings
        self.viewer.eye = (1.4, 0.0, 2.8)
        self.viewer.lookat = (-10.0, 0.0, 0.0)
        # simulation settings
        self.sim.dt = 1 / 120
        self.sim.gravity = (0.0, 0.0, -9.8)
        self.sim.render_interval = 2
        self.sim.use_fabric = True
