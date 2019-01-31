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
gi.require_version("Gtk", "3.0")
from gi.repository import GdkPixbuf, Gdk, Gtk


##
# classifier widget
#

##
# class classifier
#
# Provide the widget to classify things
#
class classifier(Gtk.Bin):


	##
	# classifier constructor
	# @param name Name of the widget
	#
	def __init__(self, name='classifier'):
		
		self.evbox     = Gtk.EventBox()
		self.hbox      = Gtk.HBox(False, 1)
		self.stars     = []
		self.enable    = False

		for s in range(5):
			sstar = star(0, s)
			sstar.connect("clicked", self.cb_star_clicked)
			self.stars.append(sstar)
			self.hbox.pack_start(self.stars[s].get_widget(), False, False, 0)

		self.evbox.add(self.hbox)
		self.evbox.set_name(name)
		self.set_value(0)


	##
	# Method of Gtk.Bin
	#
	def get_child(self):
		return(self.evbox)


	##
	# Enable/Disable hability to set classification
	# @param state True for allow classification, False just for visualization
	#
	def set_enable(self, state):

		self.enable = state

		if state == True:
			cursor = Gdk.Cursor.new(Gdk.CursorType.HAND2)
			self.evbox.get_window().set_cursor(cursor)
		else:
			self.evbox.get_window().set_cursor(None)


	##
	# Set the value of classification
	# @param val Value (0 to 4)
	# @return bool False if value is invalid, True otherwise
	#
	def set_value(self, value):
		
		if value >= 0 and value <= 4:
			self.value = value

			# update stars
			for n in range(self.value+1):
				s = self.stars[n]
				s.set_state(1)

			for i in range(self.value+1, 5):
				s = self.stars[i]
				s.set_state(0)

			return True
		else:
			return False

	##
	# Return the value of classification
	#
	def get_value(self):
		return self.value


	##
	# return the image of classification in a pixbuf
	#
	def get_pixbuf(self):

		pb = self.stars[0].get_image().get_pixbuf()
		w  = pb.get_width()
		h  = pb.get_height()

		x    = 0
		size = len(self.stars)
		draw = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, True, 8, (w * size)+1, h+1)

		for st in self.stars:
			stimg        = st.get_image()
			imgpb 		 = stimg.get_pixbuf()
			imgpb.copy_area(0, 0, w, h, draw, x, 0)
			x = x + w

		return(draw)


	##
	# callback for each star
	#
	def cb_star_clicked(self, number):
		if self.enable == True:
			self.set_value(number)


##
# start class
#
class star:

	##
	# star constructor
	# @param state 0 = off | 1 = on
	# @param pos Position in the classification (0 to 4)
	#
	def __init__(self, state=0, pos=0):

		self.widget  = Gtk.EventBox()
		self.img_off = Gtk.Image.new_from_file("radiorec/star_off.png")
		self.img_on  = Gtk.Image.new_from_file("radiorec/star_on.png")
		self.img     = Gtk.Image.new_from_pixbuf(self.img_off.get_pixbuf())
		self.set_state(state)

		if pos >= 0 and pos <= 4:
			self.pos = pos
		else:
			self.pos = 0

		self.callback = None

		self.widget.add(self.img)
		self.widget.connect("button-release-event", self.cb_on_click)


	##
	# set star state
	# @param state 0 = off | 1 = on
	#
	def set_state(self, state=0):
		if state == 0:
			self.img.set_from_pixbuf(self.img_off.get_pixbuf())
		elif state == 1:
			self.img.set_from_pixbuf(self.img_on.get_pixbuf())


	##
	# Return the widget
	# @return widget
	#
	def get_widget(self):
		return self.widget


	##
	# Return the image widget
	# @return image
	#
	def get_image(self):
		return self.img


	##
	# connect function to callback
	#
	def connect(self, eventname, cb=None):

		if eventname == "clicked":
			self.callback = cb


	##
	# callback for star
	#
	def cb_on_click(self, widget, event):
		if self.callback != None:
			self.callback(self.pos)

