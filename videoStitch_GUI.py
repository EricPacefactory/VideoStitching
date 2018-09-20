#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Jul  9 10:14:00 2018

@author: eo
"""

import os
import cv2
import numpy as np
import datetime as dt

import re

from local.lib.video.io import setupVideoCapture, setupVideoRecording
from local.lib.video.windowing import SimpleWindow, breakByKeypress, arrowKeys
from local.lib.utils.files import guiLoadMany, guiSave, guiConfirm, guiDialogEntry

# ---------------------------------------------------------------------------------------------------------------------
#%% Magic sorting functions

# Set of functions found:
# https://stackoverflow.com/questions/4623446/how-do-you-sort-files-numerically
# Author: Daniel DiPaolo

def tryint(s):
    try:
        return int(s)
    except:
        return s

def alphanum_key(s):
    """ Turn a string into a list of string and number chunks.
        "z23a" -> ["z", 23, "a"]
    """
    return [ tryint(c) for c in re.split('([0-9]+)', s) ]

def sort_nicely(l):
    """ Sort the given list in the way that humans expect.
    """
    #l.sort(key=alphanum_key)
    return sorted(l, key=alphanum_key)


# ---------------------------------------------------------------------------------------------------------------------
#%% Cropping functions
    
def rectangularize(quad_points, mouse_xy, modified_index):
    
    # Get the two opposing corners from the quadrilateral
    opposite_index = (modified_index + 2) % 4
    opposite_corner = quad_points[opposite_index]
    far_corner_list = [mouse_xy, opposite_corner]
    
    # Figure out the bounding rectangle based on the corner points
    min_x, min_y = np.min(far_corner_list, axis = 0)
    max_x, max_y = np.max(far_corner_list, axis = 0)
    
    # Build the new quad corner points
    tl = (min_x, min_y)
    tr = (max_x, min_y)
    br = (max_x, max_y)
    bl = (min_x, max_y)
    
    return np.int32([tl, tr, br, bl])

# .....................................................................................................................
    
def crop_callback(event, mx, my, flags, param):
    # Record mouse x and y positions at all times for hovering
    param["mouse_move_offset"] = max(0, min(flags, param["mouse_move_offset"]))
    mxy = np.array((mx, my)) - param["borderWH"] 
    param["mouse"] = mxy
    points_in_progress = (len(param["new_points"]) > 0)
    
    # .................................................................................................................
    # Get point hovering (as long as we're not left-click dragging)
        
    if flags != (param["mouse_move_offset"] + cv2.EVENT_FLAG_LBUTTON) and not points_in_progress:
        # Check for the closest point
        minSqDist = 1E9
        bestMatchIdx = -1
        
        for zoneIdx, eachZone in enumerate(param["zone_list"]):
            for pointIdx, eachPoint in enumerate(eachZone):
                
                # Calculate the distance between mouse and point
                distSq = np.sum(np.square(mxy - eachPoint))
                
                # Record the closest point
                if distSq < minSqDist:
                    minSqDist = distSq
                    bestMatchIdx = (zoneIdx, pointIdx)
                    
        # Record the closest zone/point if it's close enough
        distanceThreshold = 50**2            
        param["zonepoint_hover"] = bestMatchIdx if minSqDist < distanceThreshold else None
        
    # .................................................................................................................
    # Select nearest point on left click
    
    if event == cv2.EVENT_LBUTTONDOWN and not points_in_progress:

        # Select the point nearest to the mouse before clicking
        zonepointHover = param["zonepoint_hover"]
        if zonepointHover is not None:
            param["zonepoint_select"] = zonepointHover
            
    # .................................................................................................................
    # Move points on left click & drag
    
    if flags == (param["mouse_move_offset"] + cv2.EVENT_FLAG_LBUTTON) and not points_in_progress:
        
        # Update the dragged points based on the mouse position
        zonepointSelect = param["zonepoint_select"]
        if zonepointSelect is not None:
            
            # Force rectangular shape after dragging
            zone_select = zonepointSelect[0]
            point_select = zonepointSelect[1]
            new_quad = rectangularize(param["zone_list"][zone_select], mxy, point_select)

            # Update zone with rectangular quad co-ordinates            
            param["zone_list"][zone_select] = new_quad
    
    # .................................................................................................................
    # If no points-in-progress, un-select dragging points on left-release
    
    # Clear mask/point selection when releasing left click 
    if event == cv2.EVENT_LBUTTONUP and not points_in_progress:
        param["zonepoint_select"] = None
    
    # .................................................................................................................
    # If points-in-progress, complete polygon (or remove non-polygons) on left-release
    
    # Add new zone if releasing left click while in the middle of adding new points
    if event == cv2.EVENT_LBUTTONUP and points_in_progress:
        '''
        # For convenience
        new_points = param["new_points"]
        
        # Ignore cases where we don't have enough points for a polygon and just delete the record
        if len(new_points) < 3:
            param["new_points"] = []
            return
        
        # Convert to int32 numpy array for drawing purposes
        new_zone_points = np.array(param["new_points"], dtype=np.int32)
        
        # Add a new zone to the list
        param["zone_list"].append(new_zone_points)
        
        # Clear the points used to create the zone so we don't re-use them
        param["new_points"] = []
        '''
        pass
    
    # .................................................................................................................  
    # Create new points with middle click
    
    # flags == (param["mouse_move_offset"] + cv2.EVENT_FLAG_LBUTTON + cv2.EVENT_FLAG_SHIFTKEY):
    if event == cv2.EVENT_MBUTTONDOWN:
        '''
        param["new_points"].append(mxy)
        '''
        pass
    
    # .................................................................................................................
    # Delete masks with right-click
    
    if event == cv2.EVENT_RBUTTONDOWN:
        
        '''
        # Clear zone that are moused over, but only if we aren't currently drawing a new region
        if not points_in_progress:
            param["zone_list"] = [eachZone for eachZone in param["zone_list"] 
                                  if (cv2.pointPolygonTest(eachZone, tuple(mxy), measureDist=False) < 0)]
            
        # Clear mask-in-progress points regardless
        param["new_points"] = []
        param["zonepoint_select"] = None
        param["zonepoint_hover"] = None
        '''
        pass
    
# .....................................................................................................................
    
def crop_video(video_source, vidWH, vidFPS):
    
    # Set some convenient parameters
    solidBorder = cv2.BORDER_CONSTANT
    borderColor = (20,20,20)
    wBorder = 35
    hBorder = 35
    borderWH = np.array((wBorder, hBorder))
    cropping_frame_delay = int(1000/vidFPS)
    initial_crop_region_norm = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
    
    initial_crop_region = np.int32(np.array(initial_crop_region_norm)*(np.array(vidWH) - np.array((1,1))))
    
    crop_cb_data = {"mouse_move_offset": 1000000,
                    "mouse": None,
                    "borderWH": borderWH,
                    "zonepoint_hover": None,
                    "zonepoint_select": None,
                    "zone_list": [initial_crop_region],
                    "new_points": []}
    
    # Set up windowing and video capture
    videoObj, _, _ = setupVideoCapture(video_source, verbose=False)
    cropWindow = SimpleWindow("Crop Video", x = 100, y = 25)    
    cropWindow.attachCallback(crop_callback, crop_cb_data)
    
    while True:
        
        # Get video frame        
        (receivedFrame, inFrame) = videoObj.read()
        
        # Restart the video if we reach the end
        if not receivedFrame: 
            videoObj.set(cv2.CAP_PROP_POS_FRAMES, 0)
            
        # Resize the frame if needed
        scaledFrame = cv2.resize(inFrame, dsize=vidWH)
        
        # Create bordered frame for drawing crop region
        # Add borders to the frame for drawing 'out-of-bounds'
        borderedFrame = cv2.copyMakeBorder(scaledFrame, 
                                           top=hBorder, 
                                           bottom=hBorder, 
                                           left=wBorder,
                                           right=wBorder,
                                           borderType=solidBorder,
                                           value=borderColor)
        
        # Draw crop region
        crop_zone = crop_cb_data["zone_list"][0] + borderWH
        cv2.polylines(borderedFrame, [crop_zone], True, (0, 255, 255), 1, cv2.LINE_AA)        
        
        winExists = cropWindow.imshow(borderedFrame)
        if not winExists: break
    
        # Allow q/Esc to break the loop
        reqBreak, keyPress = breakByKeypress(cropping_frame_delay)
        if reqBreak: 
            break
        
        # Break on enter key
        if keyPress == 10:
            break
        
        # Allow for small adjustments using the arrow keys (adjust points closest to the mouse)
        arrowPressed, arrowXY = arrowKeys(keyPress)
        if arrowPressed:
            zonepointHover = crop_cb_data["zonepoint_hover"]
            if zonepointHover is not None:
                crop_cb_data["zone_list"][zonepointHover[0]][zonepointHover[1]] += arrowXY
        
        
    # Clean up
    videoObj.release()
    cv2.destroyAllWindows()
    
    # Get crop-coords
    crop_pt1 = crop_cb_data["zone_list"][0][0] # Top-left
    crop_pt2 = crop_cb_data["zone_list"][0][2] # Bot-right
    
    # Get cropping co-ordinates
    cropY1, cropY2 = crop_pt1[1], crop_pt2[1]
    cropX1, cropX2 = crop_pt1[0], crop_pt2[0]
    
    # Make sure pixel positions aren't out-of-bounds
    cropY1 = min(vidWH[1] - 1, max(0, cropY1))
    cropY2 = min(vidWH[1] - 1, max(0, cropY2))
    cropX1 = min(vidWH[0] - 1, max(0, cropX1))
    cropX2 = min(vidWH[0] - 1, max(0, cropX2))
    
    # Get updated video size
    new_width = 1 + cropX2 - cropX1
    new_height = 1 + cropY2 - cropY1
    newWH = (new_width, new_height)
    
    # Normalize cropping-coords, in case input videos are different sizes
    coords_px = (cropY1, cropY2, cropX1, cropX2)
    frame_scaling = (vidWH[1] - 1 , vidWH[1] - 1, vidWH[0] - 1, vidWH[0] - 1)
    coords_norm = np.float32(coords_px) / np.float32(frame_scaling)
    
    return coords_norm, newWH

# .....................................................................................................................

def apply_crop(input_frame, crop_coordinates_normalized):
    
    frame_height, frame_width = input_frame.shape[0:2]
    frame_scaling = np.float32((frame_height - 1, frame_height - 1, frame_width - 1, frame_width - 1))
    cropY1, cropY2, cropX1, cropX2 = np.int32(crop_coordinates_normalized * frame_scaling)
    
    return input_frame[cropY1:cropY2, cropX1:cropX2]

# .....................................................................................................................
    
# .....................................................................................................................
    

# ---------------------------------------------------------------------------------------------------------------------
#%% Initialize variables

# Set display timelapse. Will be overriden by recording timelapse, if one is specified
displayTL = 1

# ---------------------------------------------------------------------------------------------------------------------
#%% Load files

# Get user to select files
fileList = guiLoadMany(windowTitle="Select video files")

# Get sorted files (or at least, try to sort) so that they are stitched in the proper order
sortedFileList = sort_nicely(fileList)
totalFileCount = len(sortedFileList)

# Print out sorted file names (without paths) for user inspection:
print("")
print("*************** File list (sorted) ***************")
print("")
for eachFile in sortedFileList:
    print(os.path.basename(eachFile))
print("")
print("**************************************************")


# ---------------------------------------------------------------------------------------------------------------------
#%% Validate video list

# Try to open each video and get it's info. If this fails, better to find out now!
wh_list = []
fps_list = []
for eachVideo in sortedFileList:
    videoObj, vidWH, vidFPS = setupVideoCapture(eachVideo, verbose=False)
    videoObj.release()
    wh_list.append(vidWH)
    fps_list.append(vidFPS)
    
# Set 'target' values for video output
vidWH = max(wh_list)                    # Pick the dimensions with the highest width
vidFPS = sum(fps_list)/len(fps_list)    # Average FPS
    
# Check if there are differences in the video dimensions and provide feedback
uniqueWH = set(wh_list)
if len(uniqueWH) > 1:
    print("")
    print("Video dimensions are not all equal!")
    print("Will resize output to be consistent")

# Check for frame rate differences and provide feedback
uniqueFPS = set(fps_list)
if len(uniqueFPS) > 1:
    print("")
    print("Video FPS rates are not all equal!")
    print("Will use average FPS:", "{:.3f}".format(vidFPS))
    
# --------------------------------------------------------------------------------------------------------------------- 
#%% Set up cropping 
    
crop_coords = None
croppingEnabled = guiConfirm("Would you like to crop the video?", "Cropping")
if croppingEnabled:
    sample_video_ref = sortedFileList[0]  
    crop_coords, vidWH = crop_video(sample_video_ref, vidWH, vidFPS)
    
# ---------------------------------------------------------------------------------------------------------------------
#%% Set up video scaling

# Get video size scaling
infoString = "(Video dimensions: {} x {})".format(*vidWH)
videoScale = guiDialogEntry(dialogText="Enter video down-scaling factor:\n" + infoString, 
                            windowTitle="Scaling factor", 
                            retType=int)
videoScale = 1 if videoScale is None else videoScale

# Set up video scaling
scaledWH = (int(vidWH[0]*(1/videoScale)), int(vidWH[1]*(1/videoScale)))

# ---------------------------------------------------------------------------------------------------------------------
#%% Set up recording

videoOut = None
recordTL = displayTL
recordingEnabled = guiConfirm("Would you like to record the stitched video?", "Record video")
if recordingEnabled:
    
    # Get file save path
    outSource = guiSave(windowTitle="Save stitched video", fileTypes=[["video", "*.avi"]])
    if outSource is not None:        
        # Get timelapse factor
        infoString = "(Default: 1)"
        recordTL = guiDialogEntry(dialogText="Enter timelapse factor:\n" + infoString, 
                                  windowTitle="Timelapse factor", 
                                  retType=int)
        recordTL = 1 if recordTL is None else recordTL
        displayTL = recordTL
        print("")
        print("Using timelapse factor:", recordTL)
        
        # Get recording framerate
        infoString = "(Orignal FPS: {})".format(vidFPS)
        recordFPS = guiDialogEntry(dialogText="Enter recording framerate:\n" + infoString, 
                                  windowTitle="Recording framerate", 
                                  retType=float)
        recordFPS = vidFPS if recordFPS is None else recordFPS
        print("")
        print("Using framerate:", recordFPS)
        
        # Set up video writer
        outName = os.path.basename(outSource)
        outPath = os.path.dirname(outSource)
        videoOut = setupVideoRecording(outPath, outName, scaledWH, recFPS=recordFPS, recEnabled=True)
    else:
        # Disable recording if the save prompt is cancelled
        videoOut = None
        recordingEnabled = False

# ---------------------------------------------------------------------------------------------------------------------
#%% Video loop

# Set up windowing
displayEnabled = (not recordingEnabled)
displayWindow = SimpleWindow("Display", enabled=displayEnabled)

# Some loop-helping variables
breakFullLoop = False
frameCount = -1

try:
    for fileIdx, eachVideo in enumerate(sortedFileList):
        
        # Try to open each video file. We didn't do any safety checks beforehand...
        try:
            videoObj, _, _ = setupVideoCapture(eachVideo, verbose=False)
        except:
            print("")
            print("Error loading video file:")
            print(eachVideo)
            print("Quitting...")
            break
        
        # Some feedback
        print("")
        print("Working on video:", os.path.basename(eachVideo))
        
        # Pull frames from each video
        startTime = dt.datetime.now()
        while True:
            
            # .........................................................................................................
            # Get video frame
            
            (receivedFrame, inFrame) = videoObj.read()
            
            if not receivedFrame: break
            frameCount += 1
            
            # Only bother with the rest of the processing if we aren't timelapsing
            if frameCount % displayTL != 0 and frameCount % recordTL != 0:
                continue
            
            # Crop if needed
            if croppingEnabled:
                inFrame = apply_crop(inFrame, crop_coords)
            
            # Shrink the frame if needed
            scaledFrame = cv2.resize(inFrame, dsize=scaledWH)
            
            # .........................................................................................................
            # Add time text
            
            # Not implemented yet...
            
            # .........................................................................................................
            # Record frames
            
            if recordingEnabled:
                videoOut.write(scaledFrame)
            
            # .........................................................................................................
            # Display frame
            
            if displayEnabled:
                
                # Only show the window if not recording. Allow the closing of the window to shutdown the system
                winExists = displayWindow.imshow(scaledFrame)
                if not winExists: 
                    print("")
                    print("Stopped because window was closed!")
                    breakFullLoop = True
                    break
            
                # Allow q/Esc to break the loop
                reqBreak, keyPress = breakByKeypress(1)
                if reqBreak: 
                    print("")
                    print("Key pressed to stop!")
                    breakFullLoop = True
                    break
            
        # .............................................................................................................
        # Clean up each video
            
        # Close current video object
        videoObj.release()
        
        # Stop the loop if there is a break request
        if breakFullLoop: break
        
        # Provide feedback about timing
        endTime = dt.datetime.now()
        procTime = (endTime - startTime).total_seconds()
        filesLeft = totalFileCount - (1 + fileIdx)
        print("  Took", "{:.0f}".format(procTime), "seconds")
        if filesLeft > 0:
            print("  There are", filesLeft, "file(s) left")
            print("  Approx.", "{:.1f} minutes remaining".format(filesLeft*procTime/60.0))
        
except KeyboardInterrupt:
    print("")
    print("Keyboard cancel!")
    
    
# ---------------------------------------------------------------------------------------------------------------------
#%% Clean up 

# Close window now that we're done
cv2.destroyAllWindows()

# Stop recording
if recordingEnabled:
    videoOut.release()


# ---------------------------------------------------------------------------------------------------------------------
#%% Scrap



