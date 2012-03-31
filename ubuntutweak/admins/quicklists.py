# Ubuntu Tweak - Ubuntu Configuration Tool
#
# Copyright (C) 2012 Tualatrix Chou <tualatrix@gmail.com>
#
# Ubuntu Tweak is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# Ubuntu Tweak is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Ubuntu Tweak; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA

import os
import time
import logging
import shutil

from gi.repository import GObject, Gtk
from xdg.DesktopEntry import DesktopEntry

from ubuntutweak.common.debug import log_func
from ubuntutweak.modules  import TweakModule
from ubuntutweak.settings.gsettings import GSetting
from ubuntutweak.gui.dialogs import QuestionDialog
from ubuntutweak.utils import icon

log = logging.getLogger('QuickLists')

LAUNCHER_SETTING = GSetting('com.canonical.Unity.Launcher.favorites')


def save_to_user(func):
    def func_wrapper(self, *args, **kwargs):
        is_user_desktop_file = self.is_user_desktop_file()
        if not is_user_desktop_file:
            log.debug("Copy %s to user folder, then write it" % self.filename)
            shutil.copy(self.get_system_desktop_file(),
                        self.get_user_desktop_file())
            self.filename = self.get_user_desktop_file()
            self.parse(self.filename)

        func(self, *args, **kwargs)

        if not is_user_desktop_file:
            current_list = LAUNCHER_SETTING.get_value()
            try:
                index = current_list.index(self.get_system_desktop_file())
            except Exception, e:
                log.debug(e)
                index = current_list.index(os.path.basename(self.get_system_desktop_file()))

            current_list[index] = self.filename

            LAUNCHER_SETTING.set_value(current_list)
            log.debug("current_list: %s" % current_list)
            log.debug("Now set the current list")

    return func_wrapper


class NewDesktopEntry(DesktopEntry):
    shortcuts_key = 'X-Ayatana-Desktop-Shortcuts'
    actions_key = 'Actions'
    user_folder = os.path.expanduser('~/.local/share/applications')
    system_folder = '/usr/share/applications'
    mode = ''

    def __init__(self, filename):
        DesktopEntry.__init__(self, filename)
        log.debug('NewDesktopEntry: %s' % filename)
        if self.get(self.shortcuts_key):
            self.mode = self.shortcuts_key
        else:
            self.mode = self.actions_key

    def get_shortcut_groups(self):
        enabled_shortcuts = self.get(self.mode, list=True)

        groups = self.groups()
        groups.remove(self.defaultGroup)

        for group in groups: 
            group_name = self.get_group_name(group)
            if group_name not in enabled_shortcuts:
                enabled_shortcuts.append(group_name)

        return enabled_shortcuts

    def get_group_name(self, group):
        if self.mode == self.shortcuts_key:
            return group.split()[0]
        else:
            return group.split()[-1]

    def get_group_full_name(self, group):
        if self.mode == self.shortcuts_key:
            return u'%s Shortcut Group' % group
        else:
            return u'Desktop Action %s' % group

    @log_func(log)
    def get_name_by_group(self, group):
        return self.get('Name', self.get_group_full_name(group))

    @log_func(log)
    def get_exec_by_group(self, group):
        return self.get('Exec', self.get_group_full_name(group))

    @log_func(log)
    def get_env_by_group(self, group):
        return self.get('TargetEnvironment', self.get_group_full_name(group))

    @log_func(log)
    def is_group_visiable(self, group):
        enabled_shortcuts = self.get(self.mode, list=True)
        log.debug('All visiable shortcuts: %s' % enabled_shortcuts)
        return group in enabled_shortcuts

    @log_func(log)
    @save_to_user
    def remove_group(self, group):
        shortcuts = self.get(self.mode, list=True)
        log.debug("remove_group %s from %s" % (group, shortcuts))
        #TODO if not local
        if group in shortcuts:
            shortcuts.remove(group)
            self.set(self.mode, ";".join(shortcuts))
            self.removeGroup(self.get_group_full_name(group))
            self.write()

    @log_func(log)
    @save_to_user
    def set_group_enabled(self, group, enabled):
        shortcuts = self.get(self.mode, list=True)

        if group not in shortcuts and enabled:
            log.debug("Group is not in shortcuts and will set it to True")
            shortcuts.append(group)
            self.set(self.mode, ";".join(shortcuts))
            self.write()
        elif group in shortcuts and enabled is False:
            log.debug("Group is in shortcuts and will set it to False")
            shortcuts.remove(group)
            self.set(self.mode, ";".join(shortcuts))
            self.write()

    def is_user_desktop_file(self):
        return self.filename.startswith(self.user_folder)

    def _has_system_desktop_file(self):
        return os.path.exists(os.path.join(self.system_folder, os.path.basename(self.filename)))

    def get_system_desktop_file(self):
        if self._has_system_desktop_file():
            return os.path.join(self.system_folder, os.path.basename(self.filename))
        else:
            return ''

    def get_user_desktop_file(self):
        return os.path.join(self.user_folder, os.path.basename(self.filename))

    @log_func(log)
    def can_reset(self):
        return self.is_user_desktop_file() and self._has_system_desktop_file()

    @log_func(log)
    def reset(self):
        if self.can_reset():
            shutil.copy(self.get_system_desktop_file(),
                        self.get_user_desktop_file())
            self.parse(self.filename)


class QuickLists(TweakModule):
    __title__ = _('QuickLists Editor')
    __desc__ = _('Unity Launcher QuickLists Editor')
    __icon__ = 'plugin-unityshell'
    __category__ = 'desktop'
    __desktop__ = ['ubuntu', 'ubuntu-2d']
    __utactive__ = False

    (DESKTOP_FILE,
     DESKTOP_ICON,
     DESKTOP_NAME,
     DESKTOP_ENTRY) = range(4)

    (SHORTCUTS_GROUP,
     SHORTCUTS_NAME,
     SHORTCUTS_EXEC,
     SHORTCUTS_ENABLED,
     SHORTCUTS_ENTRY) = range(5)

    def __init__(self):
        TweakModule.__init__(self, 'quicklists.ui')

        LAUNCHER_SETTING.connect_notify(self.update_launch_icon_model)

        self.shortcuts_view.get_selection().connect('changed', self.on_shortcuts_selection_changed)
        
        self.update_launch_icon_model()

        self.add_start(self.main_paned)

    @log_func(log)
    def update_launch_icon_model(self, *args):
        self.icon_model.clear()

        for desktop_file in LAUNCHER_SETTING.get_value():
            if desktop_file.startswith('/') and os.path.exists(desktop_file):
                path = desktop_file
            else:
                if os.path.exists('/usr/share/applications/%s' % desktop_file):
                    path = '/usr/share/applications/%s' % desktop_file
                else:
                    log.debug("No desktop file avaialbe in for %s" % desktop_file)
                    continue
            entry = NewDesktopEntry(path)

            self.icon_model.append((path,\
                                    icon.get_from_name(entry.getIcon(), size=32),\
                                    entry.getName(),
                                    entry))

    def on_shortcuts_selection_changed(self, widget):
        model, iter = widget.get_selected()
        if iter:
            group = model[iter][self.SHORTCUTS_GROUP]
            entry = model[iter][self.SHORTCUTS_ENTRY]
            log.debug("Select the group: %s\n"
                      "\t\t\tName: %s\n"
                      "\t\t\tExec: %s\n"
                      "\t\t\tVisiable: %s" % (group,
                                          entry.get_name_by_group(group),
                                          entry.get_exec_by_group(group),
                                          entry.is_group_visiable(group)))
            self.remove_shortcut_button.set_sensitive(True)
        else:
            self.remove_shortcut_button.set_sensitive(False)
            self.redo_shortcut_button.set_sensitive(False)

    def on_icon_view_selection_changed(self, widget):
        model, iter = widget.get_selected()
        if iter:
            self.shortcuts_model.clear()

            entry = model[iter][self.DESKTOP_ENTRY]
            for group in entry.get_shortcut_groups():
                self.shortcuts_model.append((group,
                            entry.get_name_by_group(group),
                            entry.get_exec_by_group(group),
                            entry.is_group_visiable(group),
                            entry))
            self.redo_shortcut_button.set_sensitive(True)
            self.shortcuts_view.columns_autosize()
        else:
            self.redo_shortcut_button.set_sensitive(False)

    def on_remove_shortcut_button_clicked(self, widget):
        model, iter = self.shortcuts_view.get_selection().get_selected()
        if iter:
            group_name = model[iter][self.SHORTCUTS_GROUP]
            entry = model[iter][self.SHORTCUTS_ENTRY]
            log.debug("Try to remove shortcut: %s" % group_name)
            entry.remove_group(group_name)
            log.debug('Remove: %s succcessfully' % group_name)
            model.remove(iter)

    @log_func(log)
    def on_enable_shortcut_render(self, render, path):
        model = self.shortcuts_model
        iter = model.get_iter(path)
        entry = model[iter][self.SHORTCUTS_ENTRY]
        group = model[iter][self.SHORTCUTS_GROUP]
        is_enalbed = not model[iter][self.SHORTCUTS_ENABLED]
        entry.set_group_enabled(group, is_enalbed)
        model[iter][self.SHORTCUTS_ENABLED] = is_enalbed

    @log_func(log)
    def on_redo_shortcut_button_clicked(self, widget):
        model, iter = self.icon_view.get_selection().get_selected()
        if iter:
            name = model[iter][self.DESKTOP_NAME]

            dialog = QuestionDialog(title=_("Would you like to reset %s?") % name,
                                   message=_('If you continue, the shortcuts of %s will be set to default.') % name)
            response = dialog.run()
            dialog.destroy()

            if response == Gtk.ResponseType.YES:
                entry = model[iter][self.DESKTOP_ENTRY]
                entry.reset()
                self.on_icon_view_selection_changed(self.icon_view.get_selection())

    @log_func(log)
    def on_icon_reset_button_clicked(self, widget):
        dialog = QuestionDialog(title=_("Would you like to reset the launcher items?"),
                               message=_('If you continue, launcher will be set to default and all your current items will be lost.'))
        response = dialog.run()
        dialog.destroy()

        if response == Gtk.ResponseType.YES:
            LAUNCHER_SETTING.set_value(LAUNCHER_SETTING.get_schema_value())

    @log_func(log)
    def on_add_shortcut_button_clicked(self, widget):
        pass

    def on_row_reordered(self, model, path, iter):
        GObject.idle_add(self._do_real_recorder)

    def _do_real_recorder(self):
        new_order = []
        for row in self.icon_model:
            new_order.append(row[self.DESKTOP_FILE])

        if new_order != LAUNCHER_SETTING.get_value():
            log.debug("Order changed")
            LAUNCHER_SETTING.set_value(new_order)
        else:
            log.debug("Order is not changed, pass")