#!/usr/bin/python

import urllib2
import re
from gi.repository import Gio, GLib


class SpotifyPlayer(object):
    def __init__(self):
        self.bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        Gio.bus_watch_name(
            Gio.BusType.SESSION,
            'com.spotify.qt',
            Gio.DBusProxyFlags.NONE,
            self.connect,
            self.disconnect,
        )
        self.player = None

    def connect(self, connection, name, owner):
        self.player = Gio.DBusProxy.new_sync(
            self.bus,
            Gio.DBusProxyFlags.NONE,
            None,
            'com.spotify.qt',
            '/org/mpris/MediaPlayer2',
            'org.mpris.MediaPlayer2.Player',
            None,
        )

    def disconnect(self, connection, name):
        if self.player:
            self.player = None

    def play_pause(self):
        if self.player:
            self.player.PlayPause()

    def pause(self):
        if self.player:
            self.player.Pause()

    def next(self):
        if self.player:
            self.player.Next()

    def previous(self):
        if self.player:
            self.player.Previous()


class SpotifyNotifier(object):
    def __init__(self):
        self.metadata = None
        self.current_trackid = None
        self.bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        Gio.bus_watch_name(
            Gio.BusType.SESSION,
            'com.spotify.qt',
            Gio.DBusProxyFlags.NONE,
            self.connect,
            self.disconnect,
        )

    def connect(self, connection, name, owner):
        self.notifier = Gio.DBusProxy.new_sync(
            self.bus,
            Gio.DBusProxyFlags.NONE,
            None,
            'org.freedesktop.Notifications',
            '/org/freedesktop/Notifications',
            'org.freedesktop.Notifications',
            None,
        )
        self.spotify = Gio.DBusProxy.new_sync(
            self.bus,
            Gio.DBusProxyFlags.NONE,
            None,
            'com.spotify.qt',
            '/org/mpris/MediaPlayer2',
            'org.freedesktop.DBus.Properties',
            None,
        )
        self.spotify.connect('g-signal', self.properties_changed)
        self.metadata = self.spotify.Get(
            '(ss)',
            'org.mpris.MediaPlayer2.Player',
            'Metadata',
        )

    def disconnect(self, connection, name):
        self.metadata = None
        self.current_trackid = None

    def get_cover_url(self, trackid):
        url = 'http://open.spotify.com/track/%s' % trackid.split(':')[-1]
        tracksite = urllib2.urlopen(url).read()
        matchobject = re.search('o.scdn.co/image/(.*)"', tracksite)
        if not matchobject:
            matchobject = re.search('o.scdn.co/cover/(.*)"', tracksite)
        return 'http://open.spotify.com/image/' + matchobject.group(1)

    def fetch_cover(self, trackid):
        try:
            coverfile = urllib2.urlopen(self.get_cover_url(trackid))
            tmpfilename = '/tmp/%s.jpg' % trackid
            tmpfile = open(tmpfilename, 'w')
            data = coverfile.read()
            tmpfile.write(data)
            tmpfile.close()
            return tmpfilename
        except Exception:
            return 'icon_spotify.png'

    def show(self):
        if not self.metadata:
            return
        artist = self.metadata['xesam:artist']
        if isinstance(artist, list):
            artist = artist[0]
        album = self.metadata['xesam:album']
        trackid = self.metadata['mpris:trackid']
        title = self.metadata['xesam:title']
        year = self.metadata['xesam:contentCreated'][:4]
        cover_image = self.fetch_cover(trackid)
        print '%s - %s - (%s - %s)' % (artist, title, album, year, )
        self.notifier.Notify(
            '(susssasa{sv}i)',
            'Snotify', 0,
            cover_image,
            artist,
            '%s\n%s (%s)' % (title, album, year),
            [], {}, -1,
        )

    def properties_changed(self, connection, owner, signal, data):
        if 'Metadata' not in data[1]:
            return
        self.metadata = data[1]['Metadata']
        trackid = self.metadata.get('mpris:trackid')
        if trackid and trackid != self.current_trackid:
            self.current_trackid = trackid
            self.show()


class MediaKeyHandler():
    key_mapping = {
        'Play': 'play_pause',
        'Next': 'next',
        'Previous': 'previous',
    }

    def __init__(self):
        self.player = SpotifyPlayer()
        self.bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        self.media_keys = Gio.DBusProxy.new_sync(
            self.bus,
            Gio.DBusProxyFlags.NONE,
            None,
            'org.gnome.SettingsDaemon',
            '/org/gnome/SettingsDaemon/MediaKeys',
            'org.gnome.SettingsDaemon.MediaKeys',
            None,
        )
        self.media_keys.GrabMediaPlayerKeys('(su)', 'Spotify', 0)
        self.media_keys.connect('g-signal', self.handle_mediakey)

    def handle_mediakey(self, connection, owner, signal, data):
        key = data[1]
        if key != 'Stop':
            getattr(self.player, self.key_mapping[key])()


if __name__ == '__main__':
    spotify_notifier = SpotifyNotifier()
    mediakey_handler = MediaKeyHandler()
    GLib.MainLoop().run()
