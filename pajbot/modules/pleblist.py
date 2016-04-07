import logging
import urllib

from sqlalchemy import func

from pajbot.managers import DBManager
from pajbot.managers import ScheduleManager
from pajbot.models.command import Command
from pajbot.models.pleblist import PleblistManager
from pajbot.models.pleblist import PleblistSong
from pajbot.models.pleblist import PleblistSongInfo
from pajbot.modules import BaseModule
from pajbot.modules import ModuleSetting
from pajbot.streamhelper import StreamHelper

log = logging.getLogger(__name__)


def find_youtube_id_in_string(string):
    if len(string) < 11:
        # Too short to be a youtube ID
        return False

    if len(string) == 11:
        # Assume it's a straight up youtube ID
        return string

    if not (string.lower().startswith('http://') or string.lower().startswith('https://')):
        string = 'http://' + string

    urldata = urllib.parse.urlparse(string)

    if urldata.netloc == 'youtu.be':
        youtube_id = urldata.path[1:]
    elif urldata.netloc.endswith('youtube.com'):
        qs = urllib.parse.parse_qs(urldata.query)
        if 'v' not in qs:
            return False
        youtube_id = qs['v'][0]
    else:
        return False

    return youtube_id


class PleblistModule(BaseModule):

    # TODO: Submodule for !song command
    # Should !songrequest be a submodule in itself? Maybe.

    ID = __name__.split('.')[-1]
    NAME = 'Song requests'
    DESCRIPTION = ''
    CATEGORY = 'Feature'
    SETTINGS = [
            ModuleSetting(
                key='songrequest_command',
                label='Allow song requests through chat',
                type='boolean',
                required=True,
                default=False),
            ModuleSetting(
                key='max_song_length',
                label='Max song length (in seconds)',
                type='number',
                required=True,
                placeholder='Max song length (in seconds)',
                default=600,
                constraints={
                    'min_value': 1,
                    'max_value': 3600,
                    }),
            ModuleSetting(
                key='max_songs_per_user',
                label='# song requests active per user',
                type='number',
                required=True,
                default=2,
                constraints={
                    'min_value': 1,
                    'max_value': 3600,
                    }),
            ModuleSetting(
                key='point_cost',
                label='Point costs for requesting a song',
                type='number',
                required=True,
                default=500,
                constraints={
                    'min_value': 0,
                    'max_value': 250000,
                    }),
            ]

    def bg_pleblist_add_song(self, stream_id, youtube_id, **options):
        bot = options['bot']
        source = options['source']

        with DBManager.create_session_scope() as db_session:
            song_info = db_session.query(PleblistSongInfo).filter_by(pleblist_song_youtube_id=youtube_id).first()
            if song_info is None:
                try:
                    # XXX: Should this be a setting in the module? idk
                    PleblistManager.init(bot.config['youtube']['developer_key'])
                except:
                    log.error('No youtube key set up.')
                    bot.whisper('No youtube key set up')
                    return False

                song_info = PleblistManager.create_pleblist_song_info(youtube_id)
                if song_info is False:
                    bot.whisper(source.username, 'Invalid song given (or the YouTube API is down)')
                    return False

                db_session.add(song_info)
                db_session.commit()

            # See if the user has already submitted X songs
            num_unplayed_songs_requested = int(db_session.query(func.count(PleblistSong.id)).filter_by(stream_id=stream_id, user_id=source.id, date_played=None).one()[0])
            if num_unplayed_songs_requested >= self.settings['max_songs_per_user']:
                bot.whisper(source.username, 'You can only request {} songs at the same time!'.format(num_unplayed_songs_requested))
                return False

            # Add the song request
            song_request = PleblistSong(bot.stream_manager.current_stream.id,
                    youtube_id,
                    user_id=source.id)

            # See if the song is too long
            # If it is, make it autoskip after that time
            if song_info.duration > self.settings['max_song_length']:
                song_request.skip_after = self.settings['max_song_length']

            db_session.add(song_request)

            bot.say('{} just requested the song "{}" to be played KKona'.format(source.username_raw, song_info.title))

    def pleblist_add_song(self, **options):
        message = options['message']
        bot = options['bot']
        source = options['source']

        if message:
            # 1. Find youtube ID in message
            msg_split = message.split(' ')
            youtube_id = find_youtube_id_in_string(msg_split[0])

            if youtube_id is False:
                bot.whisper(source.username, 'Could not find a valid youtube ID in your argument.')
                return False

            # 2. Make sure the stream is live
            stream_id = StreamHelper.get_current_stream_id()
            if stream_id is None or stream_id is False:
                bot.whisper(source.username, 'You cannot request songs while the stream is offline.')
                return False

            ScheduleManager.execute_now(self.bg_pleblist_add_song, args=[stream_id, youtube_id], kwargs=options)

    def load_commands(self, **options):
        if self.settings['songrequest_command']:
            self.commands['songrequest'] = Command.raw_command(self.pleblist_add_song,
                    delay_all=0,
                    delay_user=3,
                    cost=self.settings['point_cost'])
