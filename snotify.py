#!/usr/bin/python

from dbus.mainloop.glib import DBusGMainLoop
import urllib2
import gobject
import dbus
import dbus.service
import re


class SpotifyPlayer(object):
    def __init__(self):
        self.connect()

    def connect(self):
        self.bus = dbus.Bus(dbus.Bus.TYPE_SESSION)
        self.player = dbus.Interface(
            self.bus.get_object(
                'com.spotify.qt',
                '/org/mpris/MediaPlayer2',
            ),
            'org.mpris.MediaPlayer2.Player',
        )

    def play_pause(self):
        self.player.PlayPause()

    def pause(self):
        self.player.Pause()

    def next(self):
        self.player.Next()

    def previous(self):
        self.player.Previous()


class SpotifyNotifier(dbus.service.Object):
    def __init__(self):
        self.metadata = None
        self.current_trackid = None
        self.connect()

    def connect(self):
        self.bus = dbus.Bus(dbus.Bus.TYPE_SESSION)
        self.notifier = dbus.Interface(
            self.bus.get_object(
                'org.freedesktop.Notifications',
                '/org/freedesktop/Notifications',
            ),
            'org.freedesktop.Notifications',
        )
        self.spotify = self.bus.get_object(
                'com.spotify.qt',
                '/org/mpris/MediaPlayer2',
        )
        self.spotify.connect_to_signal(
            'PropertiesChanged',
            self.properties_changed,
        )
        self.metadata = dbus.Interface(
            self.spotify,
            'org.freedesktop.DBus.Properties',
        ).Get(
            'org.mpris.MediaPlayer2.Player',
            'Metadata',
        )

    def get_cover_url(self, trackid):
        url = 'http://open.spotify.com/track/%s' % trackid.split(':')[-1]
        tracksite = urllib2.urlopen(url).read()
        matchobject = re.search('o.scdn.co/image/(.*)"', tracksite)
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
        try:
            artist = self.metadata['xesam:artist'].encode('utf-8')
        except:
            try:
                artist = self.metadata['xesam:artist'][0].encode('utf-8')
            except:
                pass
        album = self.metadata['xesam:album'].encode('utf-8')
        trackid = self.metadata['mpris:trackid'].encode('utf-8')
        title = self.metadata['xesam:title'].encode('utf-8')
        year = self.metadata['xesam:contentCreated'][:4]
        cover_image = self.fetch_cover(trackid)

        print '%s - %s - (%s - %s)' % (
            artist.decode('utf-8'),
            title.decode('utf-8'),
            album.decode('utf-8'),
            year.decode('utf-8'),
        )

        self.notifier.Notify('Spotify-notify', 0,
            cover_image, artist, '%s\n%s (%s)' % (title, album, year),
            [], {}, -1)

    def properties_changed(self, *args):
        if 'Metadata' not in args[1]:
            return
        self.metadata = args[1]['Metadata']
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

    def __init__(self, notifier=None):
        self.player = SpotifyPlayer()
        self.notifier = notifier
        self.bus = dbus.Bus(dbus.Bus.TYPE_SESSION)

        self.bus_object = self.bus.get_object(
            'org.gnome.SettingsDaemon',
            '/org/gnome/SettingsDaemon/MediaKeys',
        )

        self.bus_object.GrabMediaPlayerKeys(
            'Spotify', 0,
            dbus_interface='org.gnome.SettingsDaemon.MediaKeys',
        )

        self.bus_object.connect_to_signal(
            'MediaPlayerKeyPressed',
            self.handle_mediakey,
        )

    def handle_mediakey(self, *message):
        key = message[1]
        if key != 'Stop':
            getattr(self.player, self.key_mapping[key])()
        else:
            self.notifier.show()

if __name__ == '__main__':
    DBusGMainLoop(set_as_default=True)
    spotify_notifier = SpotifyNotifier()
    mediakey_handler = MediaKeyHandler(spotify_notifier)
    loop = gobject.MainLoop()
    spotify_notifier.show()
    loop.run()
