#
#-*-encoding:utf-8-*-

##
# radiorec 
# Copyright (C) 2010 Renê de Souza Pinto
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

import gi
gi.require_version('Gst', '1.0')
from gi.repository import GObject, Gst
import os
from threading import RLock
from threading import Thread
Gst.init(None)
import sys,traceback

##
# Playblack class
# This class implements the engine to play/record streams
# using gstreamer
# 
class playback:
	
	# Class constants
	STATE_PLAYING      = 0
	STATE_STOPPED      = 1
	STATE_PAUSED       = 2
	STATE_RECORDER_ON  = 3
	STATE_RECORDER_OFF = 4
	FORMAT_OGG         = 10
	FORMAT_MP3         = 11
	REC_IMMEDIATALY    = 20
	REC_ON_NEXT        = 21

	##
	# Constructor
	#
	def __init__(self):
		
		# Set default properties
		self.uri        	= ""
		self.state      	= playback.STATE_STOPPED
		self.recorder_state = playback.STATE_RECORDER_OFF
		self.rec_trigger	= False
		self.output_str     = "./%t"
		self.output_fmt     = playback.FORMAT_OGG
		self.ext            = ".ogg"
		self.recopt         = playback.REC_IMMEDIATALY
		self.cb_cg_track    = None
		self.ud_cg_track    = None
		self.cb_cg_time     = None
		self.ud_cg_time     = None
		self.cb_cg_state    = None
		self.ud_cg_state    = None
		self.cb_cg_buffer   = None
		self.ud_cg_buffer   = None
		self.cb_cg_duration = None
		self.ud_cg_duration = None
		self.cb_eos_reached = None
		self.ud_eos_reached = None
		self.cb_error		= None
		self.ud_error       = None

		# Properties of stream
		self.organization = "unknown"
		self.bitrate      = 0
		self.genre        = "unknown"
		self.title        = "untitled"
		self.duration     = None
                self.rec_plugged  = False


		## Gstreamer

		self.lock1 = RLock()

		# Create the pipeline
		self.pipeline = Gst.Pipeline() #Gst.Pipeline("playback")

		# uridecodebin
		self.uridec = Gst.ElementFactory.make("uridecodebin", "uridecoder")
		self.uridec.connect("pad-added", self.cb_pad_added)
		self.pipeline.add(self.uridec)


		# Create the player Bin
		self.player = Gst.Bin()
		
		queue   = Gst.ElementFactory.make("queue", "queue")
		convert = Gst.ElementFactory.make("audioconvert", "converter")
		output  = Gst.ElementFactory.make("autoaudiosink", "output")

                self.player.add(queue)
                self.player.add(convert)
                self.player.add(output)

                queue.link(convert)
                convert.link(output)

		pad = queue.get_static_pad("sink")
		self.player.add_pad(Gst.GhostPad.new("sink", pad))


		# Create recorder Bin
		self.recorder = None
		self.rplugins = self.get_rec_plugins()
		try:
			self.rplugins.index(playback.FORMAT_OGG)
			self.set_format(playback.FORMAT_OGG)
		except:
			try:
				self.rplugins.index(playback.FORMAT_MP3)
				self.set_format(playback.FORMAT_MP3)
			except:
				print "ERROR: Could not find a plugin to record sound."
				print "       Please, install gstreamer-base-plugins"


		# Create 1-to-N pipe fitting
		tee = Gst.ElementFactory.make("tee", "tee")
		teepad_0 = tee.get_request_pad("src_0")
		teepad_1 = tee.get_request_pad("src_1")

		# Add to pipeline
		#self.pipeline.add(tee, self.player)
                self.pipeline.add(tee)
                self.pipeline.add(self.player)

		# Link tee with player and recorder
		pad_p = self.player.get_static_pad("sink")
		teepad_0.link(pad_p)

		# Here the pipeline is configured only to play the stream

		bus = self.pipeline.get_bus()
		bus.add_signal_watch()
		bus.connect("message", self.cb_messages)


	##
	# create a recorder Bin
	# @param fmt Format of the recorder: OGG/MP3
	# @return bin The created Bin
	#
	def create_rec_bin(self, fmt):

		if fmt == playback.FORMAT_OGG:
			recbin  = Gst.Bin()
			queue   = Gst.ElementFactory.make("queue", "queue")
			convert = Gst.ElementFactory.make("audioconvert", "converter")
			encoder = Gst.ElementFactory.make("vorbisenc", "encoder")
			muxer   = Gst.ElementFactory.make("oggmux", "muxer")
			output  = Gst.ElementFactory.make("filesink", "output")
			
			recbin.add(queue)
                        recbin.add(convert)
                        recbin.add(encoder)
                        recbin.add(muxer)
                        recbin.add(output)
			queue.link(convert)
                        convert.link(encoder)
                        encoder.link(muxer)
                        muxer.link(output)

			pad = queue.get_static_pad("sink")
			recbin.add_pad(Gst.GhostPad.new("sink", pad))

			self.rec_plugged = False

		elif fmt == playback.FORMAT_MP3:
			recbin = Gst.Bin()
			queue   = Gst.ElementFactory.make("queue", "queue")
			convert = Gst.ElementFactory.make("audioconvert", "converter")
			encoder = Gst.ElementFactory.make("lame", "muxer")
			output  = Gst.ElementFactory.make("filesink", "output")
			
			recbin.add(queue)
                        recbin.add(convert)
                        recbin.add(encoder)
                        recbin.add(output)
                        queue.link(convert)
                        convert.link(encoder)
                        encoder.link(muxer)
                        muxer.link(output)

			pad = queue.get_static_pad("sink")
			recbin.add_pad(Gst.GhostPad.new("sink", pad))

			self.rec_plugged = False
		else:
			recbin = None

		return(recbin)


	##
	# callback for bus messages
	#
	def cb_messages(self, bus, message):
		
		t = message.type

		## Change state
		if t == Gst.MessageType.STATE_CHANGED:

			old, new, pending = message.parse_state_changed()

			if new == Gst.State.PLAYING:
				self.state = playback.STATE_PLAYING
			elif new == Gst.State.NULL:
				self.state = playback.STATE_STOPPED
			elif new == Gst.State.PAUSED:
				self.state = playback.STATE_PAUSED
			else:
				return

			if self.cb_cg_state is not None:
				self.cb_cg_state(self, self.ud_cg_state)

		## Duration
		if t == Gst.MessageType.DURATION_CHANGED:
			fmt, dur      = message.parse_duration()
			self.duration = dur
			if self.cb_cg_duration is not None:
				self.cb_cg_duration(self, self.ud_cg_duration)

		## Buffering
		if t == Gst.MessageType.BUFFERING:

			percent = message.parse_buffering()
			if self.cb_cg_buffer is not None:
				self.cb_cg_buffer(self, percent, self.ud_cg_buffer)

		## End of stream
		if t == Gst.MessageType.EOS:
			self.pipeline.set_state(Gst.State.NULL)

			self.state = playback.STATE_STOPPED
			if self.cb_cg_state is not None:
				self.cb_cg_state(self, self.ud_cg_state)

		## Error
		elif t == Gst.MessageType.ERROR:
			self.player.set_state(Gst.State.NULL)
			err, debug = message.parse_error()

			if self.cb_error is not None:
				self.cb_error(self, [err, debug], self.ud_error)
			else:
				## Somebody needs to take care of errors
				print 'playback ERROR:',err,debug
			
			self.pipeline.set_state(Gst.State.NULL)
			self.state = playback.STATE_STOPPED
			if self.cb_cg_state is not None:
				self.cb_cg_state(self, self.ud_cg_state)

		## Information
		elif t == Gst.MessageType.TAG:
			taglist    = message.parse_tag()
                        updatefile = False

			# Parse information
                        for i in range(0,taglist.n_tags()):
                                key = taglist.nth_tag_name(i)

				# Organization
				if key == "organization":
					if key != self.organization:
						self.organization = taglist.get_string(key)[1]
						updatefile = True
				# Genre
				elif key == "genre":
					if key != self.genre:
						self.genre = taglist.get_string(key)[1]
						updatefile = True
				# Bitrate
				elif key == "bitrate":
					if key != self.bitrate:
                                            if taglist.get_uint(key)[0]:
                                                self.bitrate = taglist.get_uint(key)[1]
						updatefile = True
                                                
				# Title
				elif key == "title":
					self.title = taglist.get_string(key)[1]
					self.title = self.title.replace('/','-')
					updatefile = True
					if self.cb_cg_track is not None:
						self.cb_cg_track(self, self.ud_cg_track)

                        # Update output file (if needed)
                        if updatefile:
                            self.update_output_file()


	##
	# callback for pad-added of uridecodebin
	#
	def cb_pad_added(self, src, pad):
	        tee    = self.pipeline.get_by_name("tee")
		teepad = tee.get_static_pad("sink")
		pad.link(teepad)

                #stream = pad.get_stream()
                #print stream.get_caps()
		#name = stream.get_caps()[0].get_name()
		#if name == 'audio/x-raw-float' or name == 'audio/x-raw-int':
		#	tee    = self.pipeline.get_by_name("tee")
		#	teepad = tee.get_static_pad("sink")
		#	pad.link(teepad)
		#	return False
		#else:
		#return True
                return False


	##
	# connect signals of playback
	# @param signal The signal to be connected:
	#		"on_change_track"    - Called when track was changed
	#		"on_change_time"     - Called when time was changed
	#		"on_change_state"    - Called whe the state of playback was changed
	#		"on_buffering"       - Called when playback is buffering data
	#		"on_eos_reached"     - Called on end of stream
	#		"on_change_duration" - Called when duration changed
	#		"on_error"           - Called on errors
	# @param func The user callback function
	# @param userdata User data to be passed
	# @return boolean True on success, False if signal is invalid
	#
	def connect(self, signal, func=None, userdata=None):

		if signal == "on_change_track":
			self.cb_cg_track = func
			self.ud_cg_track = userdata
		elif signal == "on_change_time":
			self.cb_cg_time = func
			self.ud_cg_time = userdata
		elif signal == "on_change_state":
			self.cb_cg_state = func
			self.ud_cg_state = userdata
		elif signal == "on_buffering":
			self.cb_cg_buffer = func
			self.ud_cg_buffer = userdata
		elif signal == "on_eos_reached":
			self.cb_eos_reached = func
			self.ud_eos_reached = userdata
		elif signal == "on_change_duration":
			self.cb_cg_duration = func
			self.ud_cg_duration = userdata
		elif signal == "on_error":
			self.cb_error = func
			self.ud_error = userdata
		else:
			return False

		return True

	
	##
	# Parse filename string and create directories (if necessary)
	# return str String parsed or None if an error was ocurred
	#
	def update_output_file(self):

		if self.organization == None and self.genre == None and \
				self.bitrate == None and self.title == None:
			return None

		dest = ""
		dirs = self.output_str.split('/')
		if len(dirs[0]) != 0:
			dest = "./"
	
		for d in dirs:
			exit = False
			while not exit:
				try:
					p = d.index('%')
					if p < len(d)-1:
						ch = d[p+1]
						if ch == 't':
							dest += d[0:p]
							dest += self.title
							d = d[p+2:]
							if self.title == None:
								return None
						elif ch == 'g':
							dest += d[0:p]
							dest += self.genre
							d = d[p+2:]
							if self.genre == None:
								return None
						elif ch == 'b':
							dest += d[0:p]
							dest += self.bitrate
							if self.bitrate == None:
								return None
							d = d[p+2:]
						elif ch == 'o':
							dest += d[0:p]
							dest += self.organization
							if self.organization == None:
								return None
							d = d[p+2:]
				except:
					dest += d
					exit  = True
			dest += "/"


		dest  = dest[0:len(dest)-1]
		dest += self.ext		

		path = os.path.dirname(dest)
		
		if self.recorder_state == playback.STATE_RECORDER_ON:
			# Check (and create) directories
			try:
				if not os.path.exists(path):
					os.makedirs(path)
			except OSError:
				print 'ERROR: could not create ' + path + '. Check permissions.'
	    		pass

			if not self.rec_plugged:
				if self.recopt == playback.REC_ON_NEXT and \
						self.rec_trigger == False:
					self.rec_trigger = True
					return None
				else:
					self.rec_trigger = True

				if self.rec_trigger:
					self.recorder_plug(dest)
			else:
                                # Check if output file name has changed
	                        filesink = self.recorder.get_by_name("output")
                                if filesink.get_property("location") == dest:
                                    return dest

				##
				# FIXME: This is a workaround (is it?) to allow the change of
				# property location from filesink element. We unplug the
				# recorder from pipeline, change his state to NULL, than
				# change location property, than re-plug recorder to pipeline.
				# There is a better ways (without unplug from pipeline)?
				# Feel free to try another approach ;)
				#
				if self.lock1.acquire(0):
					try:
                                                print "update plug/unplug"
						## Unplug recorder from pipeline
						self.pipeline.set_state(Gst.State.PAUSED)

						tee = self.pipeline.get_by_name("tee")
						teepad = tee.get_static_pad("src_1")

						rpad = self.recorder.get_static_pad("sink")
						teepad.unlink(rpad)

						self.pipeline.remove(self.recorder)

						## Change recorder state and location property of filesink
						self.recorder.set_state(Gst.State.NULL)

						filesink = self.recorder.get_by_name("output")
						filesink.set_property("location", dest)

						## Re-plug to pipeline
						self.pipeline.add(self.recorder)
						rpad = self.recorder.get_static_pad("sink")
						teepad.link(rpad)

                                                self.lock1.release()
						self.pipeline.set_state(Gst.State.PLAYING)
					except:
                                                self.lock1.release()
						print "playback ERROR: Could not plug recorder to pipeline!"
						return None

		return dest

	##
	# Get avaliable plugins for record
	# @return list List of formats supported
	#
	def get_rec_plugins(self):
		
		list = []

		# Try OGG plugins
		try:
			vorbisenc = Gst.ElementFactory.make("vorbisenc", "p_vorbisenc") 
			oggmux    = Gst.ElementFactory.make("oggmux", "p_oggmux")
			list.append(playback.FORMAT_OGG)
		except:
			pass

		# Try MP3 plugins
		try:
			lame = Gst.ElementFactory.make("lame", "p_lame")
			list.append(playback.FORMAT_MP3)
		except:
			pass

		return list


	##
	# set playback uri
	# @param uri The uri
	#
	def set_uri(self, uri):
		
		self.uri = uri
		if self.pipeline.get_state(10000) == Gst.State.PLAYING:
			self.set_state(playback.STATE_STOPPED)
			self.uridec.set_property("uri", uri)
			self.set_state(playback.STATE_PLAYING)
		else:
			self.uridec.set_property("uri", uri)


	##
	# set playback state
	# @param state The state of playback:
	#			playback.STATE_PLAYING
	#			playback.STATE_STOPPED
	#
	def set_state(self, state):

		th = callerThread(self.thread_set_state, state)
		th.start()

	## This functions needs to run only in a thread
	def thread_set_state(self, state):

		if state == playback.STATE_PLAYING:
			self.pipeline.set_state(Gst.State.PLAYING)
			self.update_output_file()

			if self.cb_cg_track is not None:
				self.cb_cg_track(self, self.ud_cg_track)

		elif state == playback.STATE_STOPPED:
			self.pipeline.set_state(Gst.State.NULL)
			self.organization = "unknown"
			self.bitrate      = 0
			self.genre        = "unknown"
			self.title        = "Untitled"
			self.duration     = None
			self.state = playback.STATE_STOPPED
                        if self.rec_plugged:
                            self.recorder_unplug()

		if self.cb_cg_state is not None:
			self.cb_cg_state(self, self.ud_cg_state)


	##
	# get playback state
	# @return state Playback state
	#
	def get_state(self):
		return self.state

	##
	# get playback uri
	# @return uri Playback uri
	#
	def get_uri(self):
		return self.uri

	##
	# set recorder state
	# @param state The recorder state:
	#			playback.STATE_RECORDER_ON
	#			playback.STATE_RECORDER_OFF
	#
	def set_recorder_state(self, state):

		if self.state == playback.STATE_PLAYING:
			if state == playback.STATE_RECORDER_ON:
				self.recorder_state = state
				self.update_output_file()
			elif state == playback.STATE_RECORDER_OFF:
				self.recorder_state = state
				self.recorder_unplug()
				self.rec_trigger = False
                                self.rec_plugged = False
			else:
				return False
		else:
			return False

	##
	# plug recorder to pipeline
	# @param filename Output filename (parsed)
	#
	def recorder_plug(self, filename):

		if self.rec_plugged:
			return False

                try:
                        print "plug"
			self.pipeline.set_state(Gst.State.PAUSED)
			self.pipeline.add(self.recorder)

			filesink = self.recorder.get_by_name("output")
			filesink.set_property("location", filename)

			tee = self.pipeline.get_by_name("tee")
			teepad = tee.get_static_pad("src_1")

			rpad = self.recorder.get_static_pad("sink")
			teepad.link(rpad)
			self.pipeline.set_state(Gst.State.PLAYING)

			self.rec_plugged = True
			return True
		except:
			print "playback ERROR: Could not plug recorder to pipeline!"
                        self.rec_plugged = False
			return False

	##
	# unplug recorder to pipeline
	#
	def recorder_unplug(self):

		if not self.rec_plugged:
			return False

		try:
                        print "unplug"
			self.pipeline.set_state(Gst.State.PAUSED)

			tee = self.pipeline.get_by_name("tee")
			teepad = tee.get_static_pad("src_1")

			rpad = self.recorder.get_static_pad("sink")
			teepad.unlink(rpad)

			self.pipeline.remove(self.recorder)
			self.recorder.set_state(Gst.State.NULL)

			self.pipeline.set_state(Gst.State.PLAYING)
			self.rec_plugged = False
			return True
		except:
			print "playback ERROR: Could not unplug recorder from pipeline!"
			return False

	##
	# get recorder state
	# @return state Recorder state
	#
	def get_recorder_state(self):
		return self.recorder_state


	##
	# get playback title
	# @return title Playback title
	#
	def get_title(self):
		return self.title


	##
	# get playback duration
	# @return dur Playback duration
	#
	def get_duration(self):
		return self.duration


	##
	# return the time of pipeline (integer - seconds)
	# @return ptime Time (integer - seconds)
	#
	def get_time(self):

		try:
			duration    = int(self.pipeline.query_position(Gst.Format.TIME)[1])
			duration   /= 1E9 # duration in seconds
			return duration
		except:
			return 0


	##
	# return the time of pipeline (formated)
	# @return ptime Formated string time
	#
	def get_time_str(self):

		if self.state == playback.STATE_STOPPED:
			return "00:00"
		else:
			duration = self.get_time()

			if duration < 60:
				dig = str(int(duration))
				if duration < 10:
					return("00:0" + dig)
				else:
					return("00:" + dig)
			else:
				hours     = int(duration / 3600)
				minutes   = int((duration / 60) - (hours * 60))
				seconds   = int(duration - (hours * 3600) - (minutes * 60))
				fmt_str   = ""

				if hours > 0:
					if hours < 10:
						fmt_str = "0" + str(hours) + ":"
					else:
						fmt_str = str(hours) + ":"

				if minutes < 10:
					fmt_str += "0" + str(minutes) + ":"
				else:
					fmt_str += str(minutes) + ":"
				
				if seconds < 10:
					fmt_str += "0" + str(seconds)
				else:
					fmt_str += str(seconds)

				return(fmt_str)


	##
	# Set output format
	#
	def set_format(self, fmt):
		try:
		    self.rplugins.index(fmt)
		    self.recorder = self.create_rec_bin(fmt)		
		except:
                        traceback.print_exc(file=sys.stdout)
			print "ERROR: The specifed format is not supported."
			self.recorder    = None
                        self.rec_plugged = False
			return False

		if fmt == playback.FORMAT_OGG:
			self.ext = ".ogg"
		elif fmt == playback.FORMAT_MP3:
			self.ext = ".mp3"

		return True

	##
	# Set output file string
	#
	def set_filename(self, filename):
		
		if filename == None:
			return False
		else:
			self.output_str = filename
			return True

	##
	# Set record option
	#
	def set_recopt(self, recopt):

		recopts = [playback.REC_IMMEDIATALY, playback.REC_ON_NEXT]
		try:
			recopts.index(recopt)
			self.recopt = recopt
			return True
		except:
			return False


##
# Class callerThread
# Call a function as a Thread
#
class callerThread(Thread):

	def __init__(self, func, *args):

		Thread.__init__(self)
		self.func = func
		self.args = args
		self.setDaemon(True)

	def run(self):
		if self.func is not None:
			self.func(*self.args)

