# VideoStitching
Script used for stitching together chunks of video. Most likely coming from a VMS system or a companion script called VideoChunker.
Includes a GUI for selecting the videos/setting recording parameters/saving output file.

Tested on:
- Ubuntu 16.04
- Python 3.5.2

Requires:
- OpenCV (3.3.1+)
- numpy
- tkinter

OpenCV can be installed from pip, but has only been tested using a manual installation.
The pip installation seems to have unreliable video recording!
Tkinter was also installed separately from pip (sudo apt install python3-tk)

Local library files are copied from eolib!