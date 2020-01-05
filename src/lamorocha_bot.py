'''
Created on Apr 17, 2019

@author: root
'''
import copy
from random import shuffle
import discord
from discord.ext import commands
import asyncio
import json
import youtube_dl
import operator

youtube_dl.utils.bug_reports_message = lambda: ''


ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0' # bind to ipv4 since ipv6 addresses cause issues sometimes
}

ffmpeg_options = {
    'options': '-vn'
}

ytdl = youtube_dl.YoutubeDL(ytdl_format_options)
ANSWER_A = '🇦'
ANSWER_B = '🇧'
ANSWER_C = '🇨'
ANSWER_D = '🇩'
CHECK_EMOJI = '✅'
X_EMOJI = '❌'
GO_EMOJI = '🏁'
MUSIC_EMOJI = '🎧'
LOCK_EMOJI = '🔒'
NEXT_EMOJI = '⏭'
TADA_EMOJI = '🎉'
#Game states
NO_QUIZ = 0
RESGISTRATION = 1
ONGOING_QUIZ = 2


class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))
        if 'entries' in data:
            # take first item from a playlist
            data = data['entries'][0]
        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)


class LaMorochaBot:
    
    def __init__(self, bot_config):
        self.bot_config= bot_config
        self.bot_token = bot_config["bot_token"]
        self.voice_channel = None
        self.voice_channel_id = bot_config["voice_channel_id"]
        with open(bot_config["music_db"]) as music_db_file:    
            music_db = json.load(music_db_file)
        self.question_queue = self.generate_questions(music_db)
        self.game_state = NO_QUIZ
        self.resgistered_users = {}
        self.user_answers = {}
        self.user_scores = {}
        self.max_questions = 2
        self.n_questions = 0
        self.bot = commands.Bot(command_prefix="!", description='LaMorochaBot')
        self.run_discord_bot()
    
    def add_user_answer(self, user, answer_emoji):
        answer_index = -1
        if answer_emoji == ANSWER_A:
            answer_index = 0
            answer_letter = " **(A.)**"
        elif answer_emoji == ANSWER_B:
            answer_index = 1
            answer_letter = " **(B.)**"
        elif answer_emoji == ANSWER_C:
            answer_index = 2
            answer_letter = " **(C.)**"
        elif answer_emoji == ANSWER_D:
            answer_index = 3
            answer_letter = " **(D.)**"
        self.user_answers[user] = {"index": answer_index, "letter": answer_letter}
        
    def generate_questions(self, music_db):
        question_queue = []
        all_authors = list(music_db.keys())
        for author in music_db:
            for music_entry in music_db[author]:
                all_authors_cp = copy.deepcopy(all_authors)
                all_authors_cp.remove(author)
                shuffle(all_authors_cp)
                question_hyps = all_authors_cp[:3]
                question_hyps.append(author)
                shuffle(question_hyps)
                music_entry["hyps"] = question_hyps
                question_queue.append([author, music_entry])
        for i in range(10):
            shuffle(question_queue)
        return question_queue
        
    def change_game_state(self, new_state):
        self.game_state = new_state
        
    def create_quiz_registration(self, resgistered_users):
        instructions = CHECK_EMOJI+"- Inscrever no quiz\n"+\
                       MUSIC_EMOJI+"- Ligar ao canal #music\n"+\
                       X_EMOJI+"- Desinscrever do quiz\n"+\
                       GO_EMOJI+"- Começar o quiz"
        resitration_embed = discord.Embed(title="**Estão abertas as inscrições para o Orquestra Quiz!**")
        resitration_embed.add_field(name="**Instruções**", value=instructions, inline=False)
        if len(resgistered_users.keys()) > 0:
            field_str = ""
            for user in resgistered_users:
                field_str += resgistered_users[user]["user_name"]
                if resgistered_users[user]["join_voice_chan"]:
                    field_str += " "+MUSIC_EMOJI
                field_str += "\n"
            field_str = field_str[:-1]
            resitration_embed.add_field(name="**Jogadores Inscritos**", value=field_str, inline=False)
        return resitration_embed
    
    def generate_question_embed(self, question_info, user_answers):
        hyps = self.current_question[1]["hyps"]
        hyps_str = "**A.** "+hyps[0]+"\n"
        hyps_str += "**B.** "+hyps[1]+"\n"
        hyps_str += "**C.** "+hyps[2]+"\n"
        hyps_str += "**D.** "+hyps[3]
        
        quiz_embed = discord.Embed()
        quiz_embed.add_field(name="**Que orquestra está a tocar?**", value=hyps_str, inline=False)
        if len(user_answers.keys()) > 0:
            user_list = ""
            for user in user_answers:
                user_list += user.split('#')[0]+" "+LOCK_EMOJI+"\n"
            user_list = user_list[:-1]
            quiz_embed.add_field(name="**Respostas Bloqueadas**", value=user_list, inline=False)
        quiz_embed.set_footer(text="Pergunta "+str(self.n_questions)+"/"+str(self.max_questions))
        return quiz_embed
    
    def get_current_ranking(self):
        score_str = ""
        i = 1
        for user, pts in sorted(self.user_scores.items(), key=operator.itemgetter(1), reverse= True):
            score_str += "**"+str(i)+".** "+user.split('#')[0]+" ("+str(pts)+" pt)\n"
            i += 1
        score_str = score_str[:-1]
        return score_str
        
    async def next_question(self, quiz_channel, voice_client):
            self.n_questions += 1
            print("Sending next question")
            self.user_answers = {}
            self.current_question = self.question_queue.pop()
            print("Current url %s"%self.current_question[1]["url"])
            quiz_embed = self.generate_question_embed(self.current_question, {})
            botmsg = await quiz_channel.send(embed=quiz_embed)
            await botmsg.add_reaction(ANSWER_A)
            await botmsg.add_reaction(ANSWER_B)
            await botmsg.add_reaction(ANSWER_C)
            await botmsg.add_reaction(ANSWER_D)
            
            music_url = self.current_question[1]["url"]
            player = await YTDLSource.from_url(music_url, loop=self.bot.loop)
            voice_client.play(player, after=lambda e: print('Player error: %s' % e) if e else None)
            
    async def lock_answer(self, channel, question_msg, user, answer_emoji):
                self.add_user_answer(user, answer_emoji)
                updated_embed = self.generate_question_embed(self.current_question, self.user_answers)
                await question_msg.edit(embed=updated_embed)
                
    async def score_question(self, channel, question_msg):
                updated_embed = self.generate_question_embed(self.current_question, {})
                corrected_answers = ""
                correct_author = self.current_question[0]
                for user in self.user_answers:
                    answer_i = self.user_answers[user]["index"]
                    answer_author = self.current_question[1]["hyps"][answer_i]
                    if answer_author == correct_author:
                        correction_emoji = CHECK_EMOJI
                        self.user_scores[user] += 1
                    else:
                        correction_emoji = X_EMOJI
                    corrected_answers += correction_emoji+" "+user.split('#')[0]+self.user_answers[user]["letter"]+"\n"
                
                score_str = self.get_current_ranking()
                corrected_answers = corrected_answers[:-1]
                updated_embed.add_field(name="**Respostas Bloqueadas**", value=corrected_answers, inline=False)
                bot_answer = "Orquestra: **"+correct_author+"**\n Nome da música: **"+self.current_question[1]["song_name"]+"**"
                updated_embed.add_field(name="**Resposta Correcta**", value=bot_answer, inline=False)
                updated_embed.add_field(name="**Ranking actual**", value=score_str, inline=False)
                await question_msg.edit(embed=updated_embed)
                await question_msg.add_reaction(NEXT_EMOJI)
                
    async def end_quiz(self, channel, question_msg):
                final_ranking = self.get_current_ranking()
                rank1_user = final_ranking.split("1.**")[1].split(" (")[0] #TODO: deal with ties
                await channel.send(TADA_EMOJI+"Parabéns "+rank1_user+", és o vencedor deste quiz orquestras!"+TADA_EMOJI)
                quiz_end_embed = discord.Embed()
                quiz_end_embed.add_field(name="**Ranking final**", value=final_ranking, inline=False)
                await channel.send(embed=quiz_end_embed)
                self.n_questions = 0
                self.user_scores = {}
                self.user_answers = {}
                self.change_game_state(NO_QUIZ)
    
    async def register_quiz(self, register_message, user, join_voice_chan):
                if user not in self.user_scores:
                    self.user_scores[user] = 0
                self.resgistered_users[user] = {"user_name":user.split('#')[0], "join_voice_chan": join_voice_chan}
                register_embed = self.create_quiz_registration(self.resgistered_users)
                await register_message.edit(embed=register_embed)
                
    async def unregister_quiz(self, register_message, user):
                if user in self.resgistered_users:
                    self.resgistered_users.pop(user)
                    register_embed = self.create_quiz_registration(self.resgistered_users)
                    await register_message.edit(embed=register_embed)
                
    async def add_to_voice_chan(self, member):
            await member.move_to(self.voice_channel)
                    
    def run_discord_bot(self):
        @self.bot.event
        async def on_ready():
            print('LaMorochaBot Ready')
            self.voice_channel = self.bot.get_channel(self.voice_channel_id)
            await self.voice_channel.connect()
            print('Connected to voice channel')
            
        @self.bot.command()
        async def stop(ctx):
            """Stops and disconnects the bot from voice"""
            await ctx.voice_client.disconnect()
        
        @self.bot.command(pass_context=True)
        async def quiz(ctx, total_questions : int = self.max_questions):
            print("Received quiz command: total_questions %d"%total_questions)
            if self.game_state == NO_QUIZ:
                print("Creating quiz registration")
                self.max_questions = total_questions
                reg_embed = self.create_quiz_registration({})
                botmsg = await ctx.message.channel.send(embed=reg_embed)
                await botmsg.add_reaction(CHECK_EMOJI)
                await botmsg.add_reaction(MUSIC_EMOJI)
                await botmsg.add_reaction(X_EMOJI)
                await botmsg.add_reaction(GO_EMOJI)
                self.change_game_state(RESGISTRATION)
        
        @self.bot.event
        async def on_raw_reaction_add(payload):
            if payload.user_id != self.bot.user.id:
                channel = self.bot.get_channel(payload.channel_id)
                msg = await channel.fetch_message(payload.message_id)
                member = msg.guild.get_member(payload.user_id)
                user = str(member)
                if self.game_state == RESGISTRATION:
                    if payload.emoji.name == CHECK_EMOJI:
                        if user not in self.resgistered_users:
                            await self.register_quiz(msg, user, False)
                    elif payload.emoji.name == MUSIC_EMOJI:
                        if user not in self.resgistered_users:
                            await self.register_quiz(msg, user, True)
                        await self.add_to_voice_chan(member)
                    elif payload.emoji.name == X_EMOJI:
                        await self.unregister_quiz(msg, user)
                    elif payload.emoji.name == GO_EMOJI:
                        self.change_game_state(ONGOING_QUIZ)
                        await self.next_question(channel, msg.guild.voice_client)
                elif self.game_state == ONGOING_QUIZ:
                    if payload.emoji.name in [ANSWER_A, ANSWER_B, ANSWER_C, ANSWER_D]:
                        if user not in self.user_answers:
                            print("Got new answer")
                            await self.lock_answer(channel, msg, user, payload.emoji.name)
                            if len(self.user_answers.keys()) == len(self.resgistered_users.keys()):
                                msg.guild.voice_client.stop()
                                await self.score_question(channel, msg)
                                if self.n_questions == self.max_questions:
                                    await self.end_quiz(channel, msg)
                    elif payload.emoji.name == NEXT_EMOJI:
                        await self.next_question(channel, msg.guild.voice_client)
                await msg.remove_reaction(payload.emoji.name, member)
                    
        self.bot.run(self.bot_token)


if __name__ == "__main__":
    bot_config_path = "./config/bot_config.json"
    with open(bot_config_path) as data_file:    
        bot_config = json.load(data_file)
    
    raid_bot = LaMorochaBot(bot_config)
