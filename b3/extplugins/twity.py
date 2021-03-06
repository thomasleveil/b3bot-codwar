#
# TwityPlugin
# Copyright (C) 2010 Sergio Gabriel Teves
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
# 01/15/2010 - 1.0.0 - SGT
# Initial
# 01/16/2010 - SGT
# add unban event
# 01/18/2010 - SGT
# remove format mark
# 08/31/2010 - SGT
# Use oAuth authentication
# 02/11/2011 - SGT - 1.0.7
# Move banlist control to ipbanlist plugin
# 03/11/2011 - SGT - 1.0.8
# Update ban event for 1.4.2
# 03/16/2011 - SGT - 1.0.9
# Fix issue in ban event
# 03/19/2011 - SGT - 1.0.10
# Fix admin search method in ban event
# Remove unused methods
# 03/20/2011 - SGT - 1.0.11
# BAN event is raised every time the banned user connect. Workaround this.
# 05/04/2011 - SGT - 1.0.12
# Fix issue in ban event handling
# 04/03/2012 - SGT - 1.0.13
# Cut text to 140 chars

__version__ = '1.0.13'
__author__  = 'SGT'

import re
import time

import tweepy

import b3, threading, time
from b3 import functions
import b3.events
import b3.plugin
import poweradminurt as padmin

#--------------------------------------------------------------------------------------------------
class TwityPlugin(b3.plugin.Plugin): 
    
    _adminPlugin = None
    _cronTab = None
        
    def onStartup(self):
        self.submark = re.compile('(\^\d)')
        self._adminPlugin = self.console.getPlugin('admin')

        if not self._adminPlugin:
            # something is wrong, can't start without admin plugin
            self.error('Could not find admin plugin')
            return False
        
        # register our commands
        if 'commands' in self.config.sections():
            for cmd in self.config.options('commands'):
                level = self.config.get('commands', cmd)
                func = self.getCmd(cmd)
                if func:
                    self._adminPlugin.registerCommand(self, cmd, level, func, None)

        self.servername = self.console.getCvar("sv_hostname").getString()
        self.api = None

        self.registerEvent(b3.events.EVT_CLIENT_BAN)
        self.registerEvent(b3.events.EVT_CLIENT_BAN_TEMP)
        self.registerEvent(b3.events.EVT_CLIENT_PUBLIC)
        self.registerEvent(b3.events.EVT_CLIENT_AUTH)

        try:
            self.registerEvent(b3.events.EVT_CLIENT_UNBAN)
        except:
            self.warning("Unable to register event EVT_CLIENT_UNBAN") 
        try:
            self.registerEvent(b3.events.EVT_BAN_BREAK)
        except:
            self.warning("Unable to register event EVT_BAN_BREAK") 
            
        self.post_update("Online - %s (%s)" % (time.strftime('%d/%m %H:%M'), b3.versionId))

        if self._cronTab:
            # remove existing crontab
            self.console.cron - self._cronTab

        if self._showAliveInterval > 0:
            self._cronTab = b3.cron.PluginCronTab(self, self.post_alive, 0, 0, '*/%s' % self._showAliveInterval)
            self.console.cron + self._cronTab
            
    def post_alive(self):
        self.post_update("All systems running - %s" % time.strftime('%d/%m %H:%M'))
        
    def getCmd(self, cmd):
        cmd = 'cmd_%s' % cmd
        if hasattr(self, cmd):
            func = getattr(self, cmd)
            return func
        return None 

    def cmd_helpme(self ,data , client, cmd=None):
        """\
        Send a message to an admin
        """
        if not data:
            if client:
                client.message('^7Invalid or missing data, try !help helpme')
            return False
        else:
            if client.maxLevel >= self._adminLevel and client.maxLevel < 90:
                client.message('^7Sos bastante grandecito para resolver las cosas por tu cuenta')
            else:
                m = "[%s] %s: %s" % (client.id, client.name, data)
                self.post_update(m)
        
    def onLoadConfig(self):
        self._key = self.config.get('settings','consumer_key')
        self._secret = self.config.get('settings','consumer_secret')
        self._token = self.config.get('settings','access_token')
        self._token_secret = self.config.get('settings','secret_token')
        self._show_password = self.config.getboolean('settings','showpassword')
        self._notifynewusers = self.config.getboolean('settings','alert_new_user')
        self._adminLevel = self.config.getint('settings','admin_level')
        self._showAliveInterval = self.config.getint('settings','show_alive_interval')
        
    def onEvent(self, event):
        if (event.type == b3.events.EVT_CLIENT_BAN or
            event.type == b3.events.EVT_CLIENT_BAN_TEMP):
            self._ban_event(event)
        elif event.type == b3.events.EVT_CLIENT_PUBLIC:
            self._public_event(event)
        try:
            if event.type == b3.events.EVT_CLIENT_UNBAN:
                self._unban_event(event)
        except:
            self.verbose("EVT_CLIENT_UNBAN not supported") 
        try:
            if event.type == b3.events.EVT_BAN_BREAK:
                client = event.client
                self.post_update("WARN: [%d] %s possible ban breaker" % (client.id, client.name))
        except:
            self.verbose("EVT_BAN_BREAK not supported")
        return
      
    def onClientConnect(self, client):
        if not client or \
            not client.id or \
            client.cid == None or \
            client.pbid == 'WORLD':
            return
        
        _timeDiff = 0
        if client.lastVisit:
            _timeDiff = self.console.time() - client.lastVisit
        else:
            _timeDiff = 1000000
            
    def post_update(self, message):
        message = "(%s) %s" % (self.servername,message)
        message = self.submark.sub('',message)
        self.debug(message)
        p = threading.Thread(target=self._twitthis, args=(message,))
        p.start()
        
    def _get_connection(self):
        try:
            self.debug("Get connection")
            auth = tweepy.OAuthHandler(self._key, self._secret)
            auth.set_access_token(self._token, self._token_secret)
            self.api = tweepy.API(auth)
        except:
            self.error(e)
            return False
        else:
            return True
        
    def _twitthis(self, message):
        if not self.api:
            if not self._get_connection():
                return
        try:
            self.debug("Post update")
            self.api.update_status(status=message[:140])
            self.debug("Message posted!")
            return
        except Exception, e:
            self.error(e)

    def _unban_event(self, event):
        message = "%s [%s] was unbanned by %s [%s]" % (event.client.name, event.client.id,event.data.name, event.data.id)
        self.post_update(message)
    
    def _ban_event(self, event):
        self.debug("Processing ban event")
        c = event.client
        lastBan = c.lastBan
        if lastBan and lastBan.adminId and lastBan.timeAdd >= c.timeEdit:
            self.debug("Banned by admin %s" % lastBan.adminId)
            admin = self._adminPlugin.findClientPrompt('@%s' % str(lastBan.adminId), None)
            s = '[%d] %s was banned by %s for %s because %s' % (c.id,
                                                                c.name,
                                                                admin.name,
                                                                functions.minutesStr(lastBan.duration),
                                                                lastBan.reason)
            self.post_update(s)
        else:
            self.debug("Banned by bot")
            
    def _public_event(self, event):
        if event.data == "":
            msg = "Server opened by %s" % event.client.name
        else:
            if self._show_password:
                msg = "Server closed by %s [%s]" % (event.client.name,event.data)
            else:
                msg = "Server closed by %s" % event.client.name
        self.post_update(msg)

def do_initial_setup():
    import b3.config
    import pprint
    
    config = b3.config.load("@b3/extplugins/conf/twity.xml")
    key = config.get('settings','consumer_key')
    secret = config.get('settings','consumer_secret')
    print "Prepare auth"
    twitter = tweepy.OAuthHandler(key, secret)
    print "Paste into browser:"
    print(twitter.get_authorization_url())
    # Get the pin # from the user and get our permanent credentials
    pin = raw_input('What is the PIN? ').strip()
    access_token = twitter.get_access_token(verifier=pin)
    
    print("oauth_token: " + access_token.key)
    print("oauth_token_secret: " + access_token.secret)
        
    # Do a test API call using our new credentials
    api = tweepy.API(twitter)
    user_timeline = api.user_timeline()

    pp = pprint.PrettyPrinter(indent=4)
    pp.pprint(user_timeline)

    print("oauth_token: " + access_token.key)
    print("oauth_token_secret: " + access_token.secret)
    
if __name__ == '__main__':
    import sys
    
    if len(sys.argv)>1 and sys.argv[1]=="setup":
        do_initial_setup()
    else:
        from b3.fake import fakeConsole
        from b3.fake import joe

        setattr(fakeConsole.game,'fs_basepath','/home/gabriel/io1')
        setattr(fakeConsole.game,'fs_game','q3ut4')
        fakeConsole.setCvar('sv_hostname','C3')

        p = TwityPlugin(fakeConsole, '@b3/extplugins/conf/twity.xml')
        p.onStartup()
        p.post_update("System test")
