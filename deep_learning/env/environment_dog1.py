#!/home/rospc/torch_gpu_ros/bin/python


#################################################################################
# Copyright 2018 ROBOTIS CO., LTD.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#################################################################################

# Authors: Gilbert #

import rospy
import numpy as np
import math
from math import pi
from geometry_msgs.msg import Twist, Point, Pose
from sensor_msgs.msg import LaserScan
from nav_msgs.msg import Odometry
from std_srvs.srv import Empty
from tf.transformations import euler_from_quaternion, quaternion_from_euler
import tf
#from respawnGoal import Respawn
import time
import rospkg
import sys
rospack = rospkg.RosPack()
env_path = rospack.get_path('deep_learning')

sys.path.append(env_path+'/env')
from target_move import MoveTarget
from bot_move import MoveBot

class Env():
    def __init__(self, action_size, real = False):
        self.goal_x = 1
        self.goal_y = 1
        self.heading = 0
        self.action_size = action_size
        self.initGoal = True
        self.get_goalbox = False
        self.position = Pose().position
        self.pub_cmd_vel = rospy.Publisher('/dog/cmd_vel', Twist, queue_size=5)
        self.sub_odom = rospy.Subscriber('/odom', Odometry, self.getOdometry)
        self.reset_proxy = rospy.ServiceProxy('gazebo/reset_world', Empty) # reset_simulation
        #self.unpause_proxy = rospy.ServiceProxy('gazebo/unpause_physics', Empty)
        #self.pause_proxy = rospy.ServiceProxy('gazebo/pause_physics', Empty)
        #self.respawn_goal = Respawn()

        #self.timer_tf = rospy.Timer(rospy.Duration(0.1), self.timertf)

        

        self.ramdom_target = False

        self.ramdom_bot = False
        self.ramdom_bot_rotate = False
        self.goalNum = 0

        self.real = real

        if not self.real:
            self.bot = MoveBot()
            self.target = MoveTarget()


        self.listener = tf.TransformListener()


    def getGoalDistace(self):
        goal_distance = round(math.hypot(self.goal_x - self.position.x, self.goal_y - self.position.y), 2)

        return goal_distance

    def timertf(self):
        (T,R) = self.listener.lookupTransform('/map', '/base_footprint', rospy.Time(0))


        self.position.x = T[0]
        self.position.y = T[1]
        #rospy.loginfo(format(self.position.x)+ " / "+format(self.position.y))

        return R[2]

    def getOdometry(self, odom):
        #rospy.loginfo("Call me?")
        yaw = self.timertf()
        #(T,R) = self.listener.lookupTransform('/map', '/base_footprint', rospy.Time(0))


        #self.position.x = T[0]
        #self.position.y = T[1]
        #self.position = odom.pose.pose.position
        #orientation = odom.pose.pose.orientation
        #orientation_list = [orientation.x, orientation.y, orientation.z, orientation.w]
        #_, _, yaw = euler_from_quaternion(orientation_list)
        #yaw = R[2]

        #rospy.loginfo(format(self.position.x)+ " / "+format(self.position.y))

        goal_angle = math.atan2(self.goal_y - self.position.y, self.goal_x - self.position.x)

        heading = goal_angle - yaw
        if heading > pi:
            heading -= 2 * pi

        elif heading < -pi:
            heading += 2 * pi

        #self.heading = round(heading, 2)

    def getState(self, scan):
        scan_range = []
        heading = float(self.heading)
        min_range = 0.15
        done = False

        for i in range(len(scan.ranges)):
            if scan.ranges[i] == float('Inf'): # pastive infinity       nan > not a number
                scan_range.append(3.5)
            elif np.isnan(scan.ranges[i]): #np.isnan(float("nan"))>>True     np.isnan(float("inf"))>>False
                scan_range.append(0)
            else:
                scan_range.append(scan.ranges[i])

        if min_range > min(scan_range) > 0:
            done = True
            

        current_distance = round(math.hypot(self.goal_x - self.position.x, self.goal_y - self.position.y),2)
        current_distance = float(current_distance)
        #rospy.loginfo(current_distance)
        #rospy.loginfo(format(self.position.x,self.position.y))
        if current_distance < 0.4:
            self.get_goalbox = True
            print("self.get_goalbox = ",self.get_goalbox)
            done = True

        return scan_range + [heading, current_distance], done

    def setReward(self, state, done, action):
        yaw_reward = []
        current_distance = state[-1]
        heading = state[-2]
	

        for i in range(7):
            angle = -pi / 4 + heading + (pi / 8 * i) + pi / 2
            tr = 1 - 4 * math.fabs(0.5 - math.modf(0.25 + 0.5 * angle % (2 * math.pi) / math.pi)[0])
            yaw_reward.append(tr)

        distance_rate = 2 ** (current_distance / self.goal_distance)
        reward = ((round(yaw_reward[action] * 5, 2)) * distance_rate)
        #print("distance_rate: ",distance_rate)
        #print("yaw: ",round(yaw_reward[action] * 5, 2))
        Reward = reward

        if done and not self.get_goalbox:
            rospy.loginfo("Collision!!")
            Reward = -200
            self.pub_cmd_vel.publish(Twist())

        #print("2self.get_goalbox = ",self.get_goalbox)
        if self.get_goalbox:
            rospy.loginfo("Goal!!")
            Reward = 200
            self.goalNum = self.goalNum + 1
            self.pub_cmd_vel.publish(Twist())

            #self.goal_x, self.goal_y = self.target.movingAt(self.goalNum,self.ramdom_target)
            #self.goal_distance = self.getGoalDistace()
            #self.get_goalbox = False
            #self.bot_stop()

        return Reward

    def step(self, action):
        max_angular_vel = 1.5
        ang_vel = ((self.action_size - 1)/2 - action) * max_angular_vel * 0.5

        vel_cmd = Twist()
        vel_cmd.linear.x = 0.3
        vel_cmd.angular.z = ang_vel
        self.pub_cmd_vel.publish(vel_cmd)

        data = None
        while data is None:
            try:
                data = rospy.wait_for_message('/scan_f', LaserScan, timeout=5)
            except:
                pass

        state, done = self.getState(data)
        reward = self.setReward(state, done, action)

        goal = self.get_goalbox
        self.get_goalbox = False

        return np.asarray(state), reward, done, goal

    def bot_stop(self):
        self.pub_cmd_vel.publish(Twist())

    def reset(self):
        if not self.real:
            rospy.wait_for_service('gazebo/reset_world')
            try:
                self.reset_proxy() #problem
            except (rospy.ServiceException) as e:
                print("gazebo/reset_simulation service call failed")

        data = None
        
        while data is None:
            try:
                data = rospy.wait_for_message('/scan_f', LaserScan, timeout=5)
            except:
                pass

        # if self.initGoal:
        #     self.goal_x, self.goal_y = self.target.movingAt(self.goalNum)
        #     self.initGoal = False
        if not self.real:
            self.goal_x, self.goal_y = self.target.movingAt(self.goalNum, self.ramdom_target) 
            self.bot.movingAt(self.ramdom_bot,self.ramdom_bot_rotate)
        else:
            (trans,rot) = self.listener.lookupTransform('/map', '/maker_tf', rospy.Time(0))
            self.goal_x, self.goal_y = trans[0], trans[1]
            #print(trans[0], trans[1])

        self.goal_distance = self.getGoalDistace()
        

        state, done = self.getState(data)
        return np.asarray(state)

