# Reserved Slots Plugin
# Copyright (C) 2011 Sergio Gabriel Teves
# 
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
#
# 10-24-2011 - 1.0.0 - SGT
# Initial version

__version__ = '1.0.0'
__author__  = 'SGT'

import b3, threading, time, thread
import b3.plugin
import b3.events
import b3.cron

#--------------------------------------------------------------------------------------------------
class ReservedslotPlugin(b3.plugin.Plugin):
   
    _warn = 5
    _cronTab = None
    _timeDiffGap = 900
    _max_clients = 999
    
    def onStartup(self):
        self.registerEvent(b3.events.EVT_CLIENT_AUTH)
        if self._cronTab:
            self.console.cron - self._cronTab
        self._cronTab = b3.cron.PluginCronTab(self, self.process_connected, minute='*/5')
        self._cronTab = b3.cron.PluginCronTab(self, self.make_room, minute='*/1')
        self.console.cron + self._cronTab

        self._adminPlugin = self.console.getPlugin('admin')
        if self._adminPlugin:
            self._adminPlugin.registerCommand(self, 'reghelp', '0-0', self.cmd_reghelp, None)

    def onLoadConfig(self):
        try:
            reserved_slots = self.config.getint('settings', 'reserved_slots')
        except:
            reserved_slots = 0
        self.debug("Reserved slots %d" % reserved_slots)
            
        try:
            self._timeDiffGap = self.config.getint('settings', 'cooldown')
        except:
            self._timeDiffGap = 900
        self.debug("Cooldown gap %d" % self._timeDiffGap)
        
        try:
            sv_maxclients = int(self.console.getCvar('sv_maxclients').getString())
            self.debug("Max clients %d" % sv_maxclients)
        except:
            self.error("Unable to determine max server clients. Using 16.")
            sv_maxclients = 16
            
        try:
            sv_privateClients = int(self.console.getCvar('sv_privateClients').getString())
            self.debug("Private clients %d" % sv_privateClients)
        except:
            self.error("Unable to determine private clients. Using 0.")
            sv_privateClients = 0
            
        self._max_clients = sv_maxclients - sv_privateClients - reserved_slots
                    
    def onEvent(self,  event):
        if event.type == b3.events.EVT_CLIENT_AUTH:
            self.onConnect(event)
    
    def onConnect(self, event):
        if not event.client or event.client.pbid == 'WORLD':
            return
        self.process_connect_event(event.client)
        
    def cmd_reghelp(self, data, client, cmd=None):
        client.message(self.getMessage('reghelp', {'name': client.name, 'id': client.id}))
        return True
        
    def process_connect_event(self, client):
        self.debug("Client connected. Level %s" % client.maxLevel)

        clients = self.console.clients.getList()
        self.debug("Total connected %s" % len(clients))
        if len(clients) > self._max_clients:
            if client.maxLevel > 0:
                t = threading.Thread(target=self.make_room)
                t.start()
            else:
                _timeDiff = 0
                if client.lastVisit:
                    _timeDiff = time.time() - client.lastVisit
                else:
                    _timeDiff = 1000000
                if _timeDiff < self._timeDiffGap:
                    self.debug("Kicked because time gap")
                    client.kick('Kick because reserved slot', silent=True)
                else:
                    self.debug("Client will be kicked")
                    t = threading.Timer(20, self._client_connected, (client,))
                    t.start()
        else:
            self.debug("Client can join")

    def make_room(self):
        self.debug("Running make room")
        clients = self.console.clients.getList()
        self.debug("Clients connected %d" % len(clients))
        if len(clients) <= self._max_clients:
           self.debug("No need to make room")
           return
        last = None
        for client in clients:
            self.verbose("Client %s level %d" % (client.name, client.maxLevel))
            if client.maxLevel == 0:
                if last is None or client.lastVisit > last.lastVisit:
                    last = client
        if last:
            self.debug("%s will be kicked" % last.name)
            last.message(self.getMessage('kick_warn', {'name': last.name, 'id': last.id}))
            time.sleep(1)
            last.message(self.getMessage('kick_warn', {'name': last.name, 'id': last.id}))
            time.sleep(5)
            last.kick('Kick because reserved slot', silent=True)
        else:
            self.debug("All clients are registered")
            
    def process_connected(self):
        self.verbose('Process connected players')
        clients = self.console.clients.getList()
        for client in clients:
            if client.maxLevel == 0:
                client.message(self.getMessage('status', {'name': client.name, 'id': client.id}))
                    
    def _client_connected(self, client):
        if client.connected:
            self.debug("Warning client before kick")
            # this requires poweradmin to keep forced
            client.setvar(self, 'paforced', 'spectator')
            self.console.write('mute %s' % (client.cid))
            self.console.write('forceteam %s %s' % (client.cid, 'spectator'))
            for i in range(0,self._warn):
                client.message(self.getMessage('welcome', {'name': client.name, 'id': client.id}))
                time.sleep(2)
                self.console.write('forceteam %s %s' % (client.cid, 'spectator'))
            client.kick('Kick because reserved slot', silent=True)
        self._working = False
        
if __name__ == '__main__':
    from b3.fake import fakeConsole
    from b3.fake import FakeClient, superadmin
    import time
    
    # first time user
    user0 = FakeClient(fakeConsole, name="New1", exactName="Joe", guid="guid0", groupBits=0, team=b3.TEAM_RED)
    user0.connections = 0
    # second time user
    user1 = FakeClient(fakeConsole, name="New2", exactName="Joe", guid="guid1", groupBits=0, team=b3.TEAM_RED)
    user1.connections = 1
    # registered user
    user2 = FakeClient(fakeConsole, name="Registered", exactName="Joe", guid="guid2", groupBits=1, team=b3.TEAM_RED)
    # regular user
    user3 = FakeClient(fakeConsole, name="Regular", exactName="Joe", guid="guid3", groupBits=4, team=b3.TEAM_RED)
    
    p = ReservedslotPlugin(fakeConsole,'conf/reservedslot.xml')
    p._max_clients = 4
    p.onStartup()
    time.sleep(10)
    
    superadmin.connects(cid=0)
    user0.connects(cid=1)
    user2.connects(cid=2)
    user3.connects(cid=3)
    user1.connects(cid=4)

    while True: time.sleep(5)
