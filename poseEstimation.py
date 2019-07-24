import tensorflow as tf
import cv2
import numpy as np
from openpose.network_mobilenet import MobilenetNetwork
import config
from tensorflow.python.client import device_lib

class OpenPose:
    def __init__(self, sess=None):
        self.sess = sess
        self.stage_level = 6
        self.input_node = tf.placeholder(tf.float32, shape=(None, config.op_input_height, config.op_input_width, 3), name='image')
        self.first_time = True
        self.net = MobilenetNetwork({'image': self.input_node}, trainable=False, conv_width=0.75, conv_width2=0.50)
        self.graph = tf.get_default_graph()
        self.net_out_1 = self.graph.get_tensor_by_name("Openpose/MConv_Stage6_L1_5_pointwise/BatchNorm/FusedBatchNorm:0")
        self.net_out_2 = self.graph.get_tensor_by_name('Openpose/MConv_Stage6_L2_5_pointwise/BatchNorm/FusedBatchNorm:0')

        # self.multi_openPose()

    def load_openpose_weights(self):
        with tf.name_scope('OpenPose_Loader'):
            s = '%dx%d' % (self.input_node.shape[2], self.input_node.shape[1])
            ckpts = './openpose/models/trained/mobilenet_' + s + '/model-release'
            vars_in_checkpoint = tf.train.list_variables(ckpts)
            var_rest = []
            for el in vars_in_checkpoint:
                var_rest.append(el[0])
            variables = tf.contrib.slim.get_variables_to_restore()
            var_list = [v for v in variables if v.name.split(':')[0] in var_rest]
            loader = tf.train.Saver(var_list=var_list)
            loader.restore(self.sess, ckpts)

    def compute_pose_frame(self, input_image):
        pafMat, heatMat = self.sess.run([self.net_out_1, self.net_out_2], feed_dict={'image:0': [input_image]})
        heatMat, pafMat = heatMat[0], pafMat[0]
        heatMat = np.amax(heatMat, axis=2)
        pafMat = np.amax(pafMat, axis=2)
        heatMat = cv2.resize(heatMat, dsize=(input_image.shape[0], input_image.shape[1]), interpolation=cv2.INTER_CUBIC)
        pafMat = cv2.resize(pafMat, dsize=(input_image.shape[0], input_image.shape[1]), interpolation=cv2.INTER_CUBIC)
        return heatMat, pafMat

    def multi_openPose(self):
        local_device_protos = device_lib.list_local_devices()
        available_gpus = [x for x in local_device_protos if x.device_type == 'GPU']
        j=0
        Net_collection = {}
        Out_collection = {}
        with tf.name_scope('Multi_openpose'):
            multi_openpose_input = tf.placeholder(tf.float32, shape=(len(available_gpus),None, config.op_input_height, config.op_input_width, 3), name='image')
            for device in available_gpus:
                with tf.device(device.name):
                    with tf.variable_scope('Open_Pose') as scope:
                        if j>0:
                            scope.reuse_variables()
                        Net_collection['Network_' + str(j)] = MobilenetNetwork({'image': multi_openpose_input[j,:, :, :, :]}, trainable=False, conv_width=0.75, conv_width2=0.50)
                        self.graph = tf.get_default_graph()
                        if j == 0:
                            net_out_1 = self.graph.get_tensor_by_name('Multi_openpose/Open_Pose/Openpose/MConv_Stage6_L1_5_pointwise/BatchNorm/FusedBatchNorm:0')
                            net_out_2 = self.graph.get_tensor_by_name('Multi_openpose/Open_Pose/Openpose/MConv_Stage6_L2_5_pointwise/BatchNorm/FusedBatchNorm:0')
                        else:
                            net_out_1 = self.graph.get_tensor_by_name('Multi_openpose/Open_Pose_' + str(j) + '/Openpose/MConv_Stage6_L1_5_pointwise/BatchNorm/FusedBatchNorm:0')
                            net_out_2 = self.graph.get_tensor_by_name('Multi_openpose/Open_Pose_' + str(j) + '/Openpose/MConv_Stage6_L2_5_pointwise/BatchNorm/FusedBatchNorm:0')

                        Out_collection['Network_' + str(j)] = [net_out_1, net_out_2]
                        # saver = tf.train.Saver(var_list={'selector_network/c2w/var1': var1})
                        j = j+1
            self.load_multi_openpose_weights

    def load_multi_openpose_weights(self):
        with tf.name_scope('OpenPose_Loader'):
            s = '%dx%d' % (self.input_node.shape[2], self.input_node.shape[1])
            ckpts = './openpose/models/trained/mobilenet_' + s + '/model-release'
            vars_in_checkpoint = tf.train.list_variables(ckpts)
            var_rest = []
            for el in vars_in_checkpoint:
                var_rest.append(el[0])
            variables = tf.contrib.slim.get_variables_to_restore()
            var_list = [v for v in variables if v.name.split(':')[0] in var_rest]
            var_list = {}
            for v_rest in var_rest:
                for v_graph in variables:
                    if v_rest.name.split(':')[0] in v_graph.name.split(':')[0]:
                        var_list[v_graph.name.split(':')[0]] = v_rest
                        break
            print(var_list)
            loader = tf.train.Saver(var_list=var_list)
            loader.restore(self.sess, ckpts)
