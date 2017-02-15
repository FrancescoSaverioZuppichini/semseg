'''
This script computes the bounding boxes of each gt object,
and return the upper-left corner of the box.
'''


from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import numpy as np
from PIL import Image
import math
import sys
import os
import glob
from scipy import sparse
from scipy.misc import toimage
from scipy.misc import imsave
#import matplotlib.pyplot as plt

import Stat_Boxes

MAX_instances = 30
Box_Width = 392
Box_Height = 448

def cal_precise_positive(img_mask, inst_num):
    '''
    Give precise coordinate of positive box.
    '''

    where = np.equal(img_mask, inst_num)
    indices = np.where(where)

    np_indices = np.array(indices)
    if not np_indices.size:
        return None, None, None, None, None

    min_x = indices[0].min()
    min_y = indices[1].min()
    max_x = indices[0].max()
    max_y = indices[1].max()
    obj_num = inst_num

    return min_x, min_y, max_x, max_y, obj_num

def get_precise_posiboxes_of_Mask(fname):
    list_of_preposiboxes = []
    img, img_shape = Stat_Boxes.open_gt_file(fname)
    #print('The shape of the image is: ', img_shape)

    for inst_num in range(MAX_instances):
    	(x_min, y_min, x_max, y_max, obj_num) = cal_precise_positive(img[:,:,1], inst_num+1)
        if x_min is not None:
            list_of_preposiboxes.append([x_min, y_min, x_max, y_max, obj_num])

    return list_of_preposiboxes


def is_positive(precise_pos_list, test_coord):
    '''
    for the test_coord, test if it is a positive box
    '''

    for precise_coord in precise_pos_list:
    	# Compute the potential positive box coord
    	pre_box_coord, pre_box_dim, obj_num = generate_precise_posiBox(precise_coord)
    	if pre_box_coord is None:
    		continue
    	else:
    		# Test if the tested coord is considered as a positive box
    		if abs(pre_box_coord[0] - test_coord[0][0]) <= 16 and abs(pre_box_coord[0] - test_coord[0][1]) <= 16:
    			# The test_coord is a positive box
    			return True

    return False

def random_pair(rand_type):
    '''
    rand_type: positive, negative
    '''
    if rand_type == 'positive':
        rand_num = np.random.randint(-16,16)

    # the random number generated is still between -448 and 448,
    # since it covers most of the dimensions of boxes.
    # Attension: may need a better random generator.
    elif rand_type == 'negative':
        rand_num = np.random.randint(-448,448)
        if rand_num >= 0 and rand_num <= 16:
            rand_num += 16
        elif rand_num <= 0 and rand_num >= -16:
            rand_num -= 16
    else:
        sys.exit('Invalid rand_type. Must be positive or negative')

    return rand_num


def generate_box(fname):
	#box_data = {}
	box_data = []
	nega_box_none = False
	#box_data['positive'] = []
	#box_data['negative'] = []

	list_of_preposiboxes = get_precise_posiboxes_of_Mask(fname)
	number_of_preposiboxes = len(list_of_preposiboxes)
	if number_of_preposiboxes == 0:
		loop_num = 0
		loop_remainder = 0
		print('No usable boxes for this image. Return None.')
		return None
	else:
		loop_num = int(128 / number_of_preposiboxes)
		loop_remainder = int(128 % number_of_preposiboxes)
	invalid_remainder = 0
	# Generating 128 positive and negative boxes, respectively.
	#print('Number of tight box: ', number_of_preposiboxes)
	#print('Number of loop_num: ', loop_num)
	#print('Number of loop_remainder: ', loop_remainder)
	for index in range(loop_num):
		for pre_coord in list_of_preposiboxes:
			nega_box_none = False
			# Generate positive box
			posi_box = generate_positive_box(pre_coord)

			# If the posi_box is none, this indicates that the box is invalid, skip this loop
			if posi_box is None:
				invalid_remainder += 1
				continue
			else:
				#box_data['positive'].append(posi_box)
				box_data.append(posi_box)

			# Generate negative box
			nega_box = generate_negative_box(pre_coord)
			if nega_box is None:
				invalid_remainder += 1
				# remove the corresponding positive box
				box_data.pop()
				continue
			else:
				# If the negative box is not overlap with another positive box
				while is_positive(list_of_preposiboxes, nega_box):
					nega_box = generate_negative_box(pre_coord)
					if nega_box is None:
						nega_box_none = True
						invalid_remainder += 1
						# remove the corresponding positive box
						box_data.pop()
						break
				if nega_box_none:
					continue
				else:
					box_data.append(nega_box)

	# Generate for the remainder boxes.
	if invalid_remainder == loop_num * number_of_preposiboxes:
		print('No usable boxes for this image. Return None.')
		return None
	loop_remainder += invalid_remainder
	#print('Number of positives: ', len(box_data['positive']))
	#print('Number of negatives: ', len(box_data['negative']))
	#print('Number of remainder: ', loop_remainder)
	count = 0
	while loop_remainder != 0:
		for pre_coord in list_of_preposiboxes:
			if loop_remainder == 0:
				break
			# Generate positive box
			posi_box = generate_positive_box(pre_coord)
			if posi_box is None:
				#loop_remainder += 1
				continue
			else:
				box_data.append(posi_box)
				count += 1

			# Generate negative box
			nega_box = generate_negative_box(pre_coord)
			# If the negative box is not overlap with another positive box
			while is_positive(list_of_preposiboxes, nega_box):
				nega_box = generate_negative_box(pre_coord)
			box_data.append(nega_box)
			loop_remainder -= 1

	#print('Count is: ', count)
	#print('Number of boxes in total: ', len(box_data))
	if len(box_data) != 256:
		sys.exit('Number of boxes is not 256, is: ', len(box_data))
	return box_data

def generate_positive_box(precise_posi_coord):
	'''
	Compute the randomized upper left corner of positive box.
	If there's a valid positive box, return it; Otherwise, return None.
	'''

	rand_shift = random_pair('positive')
	pre_box_coord, pre_box_dim, obj_num = generate_precise_posiBox(precise_posi_coord)

	if pre_box_coord is None:
		return None

	# Randomly shift the precise box by +- 16 pixel in both directions
	temp_x = pre_box_coord[0] + rand_shift
	temp_y = pre_box_coord[1] + rand_shift

	# Adjust box location to fit training
	x_remainder = temp_x % 8
	y_remainder = temp_y % 8
	temp_x += cal_coord_adjust(x_remainder)
	temp_y += cal_coord_adjust(y_remainder)


	if temp_y + pre_box_dim[1] >= 2048 or temp_y < 0:
		# shift to the other direction
		temp_y = pre_box_coord[1] - rand_shift
		y_remainder = temp_y % 8
		if np.sign(-rand_shift) >= 0:
			temp_y = temp_y + 8 - y_remainder
		else:
			temp_y = temp_y - y_remainder
	if temp_x + pre_box_dim[0] >= 1024 or temp_x < 0:
		temp_x = pre_box_coord[0] - rand_shift
		x_remainder = temp_x % 8
		if np.sign(-rand_shift) >= 0:
			temp_x = temp_x + 8 - x_remainder
		else:
			temp_x = temp_x - x_remainder

	posi_box = ((temp_x, temp_y), (pre_box_dim[0], pre_box_dim[1]), (1, obj_num))

	if posi_box[1][0] % 24 !=0 or posi_box[1][1] % 24 !=0:
		sys.exit('The posi box size is not a multiple of 24')
	if posi_box[0][0] % 8 !=0 or posi_box[0][1] % 8 !=0:
		sys.exit('The posi box location is not a multiple of 8')

	# reassure the box dimension
	if posi_box[0][0] + posi_box[1][0] >= 1024 or posi_box[0][1] + posi_box[1][1] >= 2048:
		#sys.exit('The posi box dimension out of boundary.')
		print('The posi box dimension out of boundary. Return None.')
		return None
	if posi_box[0][0] < 0 or posi_box[0][1] < 0:
		#sys.exit('The posi box location out of boundary, small than 0')
		print('The posi box location out of boundary, small than 0. Return None.')
		return None

	return posi_box

def generate_precise_posiBox(precise_posi_coord):
	'''
	This function generates the precise positive box for the given object.
	'''
	x_min = precise_posi_coord[0]
	y_min = precise_posi_coord[1]
	x_max = precise_posi_coord[2]
	y_max = precise_posi_coord[3]
	obj_num = precise_posi_coord[4]

	x_len = x_max - x_min
	y_len = y_max - y_min
	pre_box_coord_t = [x_min - 32, y_min - 32]
	pre_box_dim_t = [x_len + 64, y_len + 64]

	# Modify box size to fit training
	# Adjusting box size
	width_remainder = pre_box_dim_t[0] % 24
	height_remainder = pre_box_dim_t[1] % 24
	shift_coord_x = int(width_remainder / 2)
	shift_coord_y = int(height_remainder / 2)
	#shrinking the size
	pre_box_dim_t[0] -= width_remainder
	pre_box_dim_t[1] -= height_remainder
	pre_box_coord_t[0] += shift_coord_x
	pre_box_coord_t[1] += shift_coord_y

	# To tuple
	pre_box_coord = (pre_box_coord_t[0], pre_box_coord_t[1])
	pre_box_dim = (pre_box_dim_t[0], pre_box_dim_t[1])

	# Check the box is within the image boundary
	if pre_box_coord[0] >= 0 and pre_box_coord[1] >= 0:
		if pre_box_coord[0] + pre_box_dim[0] < 1024:
			if pre_box_coord[1] + pre_box_dim[1] < 2048:
				return pre_box_coord, pre_box_dim, obj_num

	return None, None, None

def cal_coord_adjust(remainder):

	if remainder <= 4 and remainder >=0:
		return -remainder
	elif remainder < 8:
		return 8-remainder
	else:
		sys.exit('Invalid x_remainder or y_remainder!')


def generate_negative_box(precise_posi_coord):
	'''
	Compute the randomized upper left corner of negative box.
	If the precise positive box is valid, then use it to generate negative box,
	otherwise, return None.
	'''
	rand_shift = random_pair('negative')
	pre_box_coord, pre_box_dim, obj_num = generate_precise_posiBox(precise_posi_coord)

	if pre_box_coord is None:
		return None

	# Randomly shift the precise box by +- at least 16 pixel in both directions
	temp_x = pre_box_coord[0] + rand_shift
	temp_y = pre_box_coord[1] + rand_shift

	# Adjust box location to fit training
	x_remainder = temp_x % 8
	y_remainder = temp_y % 8
	temp_x += cal_coord_adjust(x_remainder)
	temp_y += cal_coord_adjust(y_remainder)

	if temp_y + pre_box_dim[1] >= 2048 or temp_y < 0:
		# shift to the other direction
		if abs(rand_shift) <= 40:
			rand_shift = -rand_shift
		else:
			rand_shift = - (rand_shift / 2)
		temp_y = pre_box_coord[1] + rand_shift
		#temp_y = pre_box_coord[1] - rand_shift
		y_remainder = temp_y % 8
		if np.sign(-rand_shift) >= 0:
			temp_y = temp_y + 8 - y_remainder
		else:
			temp_y = temp_y - y_remainder
	if temp_x + pre_box_dim[0] >= 1024 or temp_x < 0:
		# if the rand_shift is within 40, then shifting to the other direction
		if abs(rand_shift) <= 40:
			rand_shift = -rand_shift
		# if the rand_shift is larger than 40, divide by 2 and then shifting to the other direction
		else:
			rand_shift = - (rand_shift / 2)
		temp_x = pre_box_coord[0] + rand_shift

		# print('before box origin, ', pre_box_coord[0])
		# print('before location temp_x, ', temp_x)
		# print('before boundary, ', temp_x + pre_box_dim[0])
		# temp_x = pre_box_coord[0] - rand_shift
		# print('middle location, ', temp_x)
		# print('middle boundary, ', temp_x + pre_box_dim[0])
		x_remainder = temp_x % 8
		if np.sign(-rand_shift) >= 0:
			temp_x = temp_x + 8 - x_remainder
		else:
			temp_x = temp_x - x_remainder
		# print('after location, ', temp_x)
		# print('after boundary, ', temp_x + pre_box_dim[0])

	nega_box = ((temp_x, temp_y), (pre_box_dim[0], pre_box_dim[1]), (0,-1))

	if nega_box[1][0] % 24 !=0 or nega_box[1][1] % 24 !=0:
		sys.exit('The nega box size is not a multiple of 24')
	if nega_box[0][0] % 8 !=0 or nega_box[0][1] % 8 !=0:
		sys.exit('The nega box location is not a multiple of 8')

	if nega_box[0][0] + nega_box[1][0] >= 1024 or nega_box[0][1] + nega_box[1][1] >= 2048:
		print('x size: ', nega_box[0][0] + nega_box[1][0])
		print('y size: ', nega_box[0][1] + nega_box[1][1])
		#sys.exit('The nega box dimension out of boundary.')
		print('The nega box dimension out of boundary. Return None.')
		return None
	if nega_box[0][0] < 0 or nega_box[0][1] < 0:
		print('x location: ', nega_box[0][0])
		print('y location: ', nega_box[0][1])
		#sys.exit('The nega box location out of boundary, small than 0')
		print('The nega box location out of boundary, small than 0. Return None')
		return None

	return nega_box

def main():

    if 'CITYSCAPES_DATASET' in os.environ:
        cityscapesPath = os.environ['CITYSCAPES_DATASET']
    else:
    	sys.exit('No data path found')

    files = Stat_Boxes.get_file_list(cityscapesPath)
    progress = 0
    print("Progress: {:>3} %".format( progress * 100 / len(files) ))
    for fname in files:
    	box_data = generate_box(fname)
    	fname = fname.replace('mask.png', 'box.npy')
    	np.save(fname, box_data)
    	progress += 1
    	print("\rProgress: {:>3} %".format( progress * 100 / len(files) ))
    	sys.stdout.flush()
    	#print('write box file to %s'%fname)

if __name__ == "__main__":
    main()