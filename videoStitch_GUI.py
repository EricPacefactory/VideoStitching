#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Jul  9 10:14:00 2018

@author: eo
"""

import os
import cv2
import datetime as dt

import re

from local.lib.video.io import setupVideoCapture, setupVideoRecording
from local.lib.video.windowing import SimpleWindow, breakByKeypress
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
        recordTL = guiDialogEntry(dialogText="Enter timelapse factor:", 
                                  windowTitle="Timelapse factor", 
                                  retType=int)
        recordTL = 1 if recordTL is None else recordTL
        displayTL = recordTL
        print("")
        print("Using timelapse factor:", recordTL)
        
        # Set up video writer
        outName = os.path.basename(outSource)
        outPath = os.path.dirname(outSource)
        videoOut = setupVideoRecording(outPath, outName, scaledWH, recFPS=vidFPS, recEnabled=True)
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
            videoObj, vidWH, vidFPS = setupVideoCapture(eachVideo, verbose=False)
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



