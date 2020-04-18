# -*- coding: UTF-8 -*-
#A part of the EnhancedDictionaries addon for NVDA
#Copyright (C) 2020 Marlon Sousa
#This file is covered by the GNU General Public License.
#See the file COPYING.txt for more details.

import config
from . import dictHelper
import gui
from gui import guiHelper
from logHandler import log
import speechDictHandler
import os
import wx


# we need to redirect some menus to trigger our specific dictionary dialog instead of NVDA one
# This is needed because aparently wx stores the address of the methods bound to menus activation, so patching the class is not enough, we need to bind the menus again
# NVDA menus are created with id WX_ANY, so it is not possible to rely on menu ids when retrieving them
# because of that, we had some options:
# - getting menus based on their position, risky because if NVDA ever changes menu positioning the addon will break
# - getting menus by their label. This is saffer, butharder, cinse menu labels are localized to the language nvda is using
# what we did is we searched for the current string equivalent to the original menu label, using the exact same translation routin NVDA uses to translate it.

def findMenuItem(menu, name):
	log.debug(f"Searching for {name}")
	return menu.FindItemById(menu.FindItem(name))


def getDictionariesMenu():
	preferencesMenu = gui.mainFrame.sysTrayIcon.preferencesMenu
	dictionaryMenu = findMenuItem(preferencesMenu, _("Speech &dictionaries"))
	if not dictionaryMenu:
		return None
	return dictionaryMenu.GetSubMenu()


def getDefaultDictionaryMenu():
	dictionariesMenu = getDictionariesMenu()
	if not dictionariesMenu:
		return None
	return findMenuItem(dictionariesMenu, _("&Default dictionary..."))


def getVoiceDictionaryMenu():
	dictionariesMenu = getDictionariesMenu()
	if not dictionariesMenu:
		return None
	return findMenuItem(dictionariesMenu, _("&Voice dictionary..."))

def rebindMenu(menu, handler):
	gui.mainFrame.sysTrayIcon.Unbind(wx.EVT_MENU, menu)
	gui.mainFrame.sysTrayIcon.Bind(wx.EVT_MENU, handler, menu)

def showEnhancedDictionaryDialog(dic, title = None):
	gui.mainFrame._popupSettingsDialog(EnhancedDictionaryDialog, title or _("Default dictionary"), dic)

# This is our new dictionary dialog.
# it presents the following changes compared to the original dialog:
# - the title of the dialog contains the profile this dictionary belongs to
# for dictionaries belonging to specific profiles, a button to import entries from the default profile dictionary is presented
# if a dictionary is being created (it does not exist on disc) it is activated imediately after the dialog closes

class EnhancedDictionaryDialog(gui.settingsDialogs.DictionaryDialog):
	
	PATTERN_COL = 1
	
	def __init__(self, parent,title,speechDict):
		self._profile = config.conf.getActiveProfile()
		title = self._makeTitle(title)
		log.debug(f"exibido {self._makeTitle(title)}")
		super(EnhancedDictionaryDialog, self).__init__(parent,title,speechDict)
	
	def _makeTitle(self, title):
		# Translators: The profile name for normal configuration
		profileName = self._profile.name or _("normal configuration")
		log.debug(f"will return {title} - {profileName}")
		return f"{title} - {profileName}"
	
	def makeSettings(self, settingsSizer):
		sHelper = guiHelper.BoxSizerHelper(self, sizer=settingsSizer)
		# Translators: The label for the list box of dictionary entries in speech dictionary dialog.
		entriesLabelText=_("&Dictionary entries")
		self.dictList = sHelper.addLabeledControl(
			entriesLabelText,
			wx.ListCtrl, style=wx.LC_REPORT | wx.LC_SINGLE_SEL
		)
		# Translators: The label for a column in dictionary entries list used to identify comments for the entry.
		self.dictList.InsertColumn(0,_("Comment"),width=150)
		# Translators: The label for a column in dictionary entries list used to identify pattern (original word or a pattern).
		self.dictList.InsertColumn(1,_("Pattern"),width=150)
		# Translators: The label for a column in dictionary entries list and in a list of symbols from symbol pronunciation dialog used to identify replacement for a pattern or a symbol
		self.dictList.InsertColumn(2,_("Replacement"),width=150)
		# Translators: The label for a column in dictionary entries list used to identify whether the entry is case sensitive or not.
		self.dictList.InsertColumn(3,_("case"),width=50)
		# Translators: The label for a column in dictionary entries list used to identify whether the entry is a regular expression, matches whole words, or matches anywhere.
		self.dictList.InsertColumn(4,_("Type"),width=50)
		self.offOn = (_("off"),_("on"))
		for entry in self.tempSpeechDict:
			self.dictList.Append((entry.comment,entry.pattern,entry.replacement,self.offOn[int(entry.caseSensitive)],EnhancedDictionaryDialog.TYPE_LABELS[entry.type]))
		self.editingIndex=-1

		bHelper = guiHelper.ButtonHelper(orientation=wx.HORIZONTAL)
		bHelper.addButton(
			parent=self,
			# Translators: The label for a button in speech dictionaries dialog to add new entries.
			label=_("&Add")
		).Bind(wx.EVT_BUTTON, self.OnAddClick)

		bHelper.addButton(
			parent=self,
			# Translators: The label for a button in speech dictionaries dialog to edit existing entries.
			label=_("&Edit")
		).Bind(wx.EVT_BUTTON, self.OnEditClick)

		bHelper.addButton(
			parent=self,
			# Translators: The label for a button in speech dictionaries dialog to remove existing entries.
			label=_("&Remove")
		).Bind(wx.EVT_BUTTON, self.OnRemoveClick)

		# name of the default profile is always set to None on NVDA
		if(self._profile.name):
			bHelper.addButton(
				parent=self,
				# Translators: The label for the import entries from default profile dictionary
				label=_("&import entries from default profile dictionary")
			).Bind(wx.EVT_BUTTON, self.onImportEntriesClick)

		sHelper.addItem(bHelper)

	def hasEntry(self, pattern):
		for row in range(self.dictList.GetItemCount()):
			if self.dictList.GetItem(row, self.PATTERN_COL).GetText() == pattern:
				return True
		return False

	def onOk(self,evt):
		newDictionary = not os.path.exists(self.speechDict.fileName)
		super().onOk(evt)
		if newDictionary:
			# if we are saving a dictionary that didn't exist before (user just performed the first edition)
			# we have to activate it now, otherwise it will be effective only on next profile switch.
			log.debug(f"Activating new dictionary {self.speechDict.fileName}")
			dictHelper.reloadDictionaries()

	def onImportEntriesClick(self, evt):
		sourceFileName = self.speechDict.fileName.replace(f"{self._profile.name}\\", "")
		log.debug(f"Importing entries from default dictionary at {sourceFileName}")
		source = speechDictHandler.SpeechDict()
		source.load(sourceFileName)
		self.tempSpeechDict.syncFrom(source)
		for entry in self.tempSpeechDict:
			if not self.hasEntry(entry.pattern):
				self.dictList.Append((
					entry.comment,
					entry.pattern,
					entry.replacement,
					self.offOn[int(entry.caseSensitive)],
					EnhancedDictionaryDialog.TYPE_LABELS[entry.type]
				))
		self.dictList.SetFocus()

