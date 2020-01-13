from apiclient.discovery import build
import json
import pafy
from tqdm import tqdm
from fuzzywuzzy import fuzz
import os
import html

YOUTUBE_API_SERVICE_NAME = "youtube"
YOUTUBE_API_VERSION = "v3"


def youtube_search(q, dev_key, max_results=50, page_token=None, videos=[]):
    youtube = build(YOUTUBE_API_SERVICE_NAME, YOUTUBE_API_VERSION, developerKey=dev_key)

    search_response = youtube.search().list(
        q=q,
        pageToken=page_token,
        type="video",
        order="relevance",
        part="id,snippet"
    ).execute()

    for search_result in search_response.get("items", []):
        if search_result["id"]["kind"] == "youtube#video":
            videos.append(search_result)

    if len(videos) < max_results:
        if "nextPageToken" in search_response:
            next_page_token = search_response["nextPageToken"]
            return youtube_search(q, dev_key, max_results=max_results, page_token=next_page_token, videos=videos)
        else:
            return videos
    else:
        return videos[0:max_results]


def add_video_len(video_search_results):
    video_dur = []
    for i in tqdm(range(len(video_search_results))):
        v = video_search_results[i]
        v_id = v['id']['videoId']
        url = "http://www.youtube.com/watch?v="+v_id
        video = pafy.new(url)
        v['snippet']['duration'] = video.length
        video_dur.append(v)
    return video_dur


def filter_duration(data_file_path, min_secs, max_secs, out_dir, out_file_path):
    with open(data_file_path, 'r') as f:
        video_search_results = json.load(f)

    filtered_videos = []
    for v in video_search_results:
        dur = v['snippet']['duration']
        if dur <= max_secs and dur >= min_secs:
            filtered_videos.append(v)

    save_data(out_dir, out_file_path, filtered_videos)


def filter_duplicates(data_file_path, max_fuzz_ratio, out_dir, out_file_path):
    with open(data_file_path, 'r') as f:
        video_search_results = json.load(f)
    query =  data_file_path.split('/')[-1].split('.')[0].lower()
    filtered_videos = []
    dups = []
    for i in range(len(video_search_results)):
        title_i = video_search_results[i]['snippet']['title'].lower().replace(query, '').strip()
        found_dup = False
        for j in range(i+1, len(video_search_results)):
            title_j = video_search_results[j]['snippet']['title'].lower().replace(query, '').strip()
            fuzz_ratio = fuzz.ratio(title_i, title_j)
            if fuzz_ratio > max_fuzz_ratio:
                found_dup = True
                dups.append([title_i, title_j, fuzz_ratio])
                break
        if not found_dup:
            filtered_videos.append(video_search_results[i])

    save_data(out_dir, out_file_path, filtered_videos)
    '''
    for d1, d2 , fuzz_ratio in dups:
        print('%s\n%s\nfuzz_ratio: %d\n==========' % (d1, d2, fuzz_ratio))
    print('Total different: %d'%(len(filtered_videos)))
    '''


def make_song_db(dir_path, out_dir, out_file_path):
    db = {}
    for file_name in os.listdir(dir_path):
        if file_name.endswith('.nd'):
            artist = file_name.split('.')[0]
            db[artist] = []
            with open(dir_path+file_name, 'r') as f:
                search_results = json.load(f)

            for sr in search_results:
                song_name = html.unescape(sr['snippet']['title'])
                url = 'https://www.youtube.com/watch?v='+sr['id']['videoId']
                db[artist].append({'song_name': song_name, 'url': url})
    save_data(out_dir, out_file_path, db)


def save_data(out_dir, out_file_path, data):
    with open(out_dir+out_file_path, 'w+') as outfile:
        outfile.write(json.dumps(data, indent=4))


MAX_FUZZ_RATIO = 75
QUERY_YOUTUBE= False
QUERIES=['Francisco Canaro',
         'Carlos Di Sarli',
         'Juan D\'Arienzo',
         'Osvaldo Pugliese',
         'Rodolfo Biagi',
         'Julio de Caro']
if __name__ == "__main__":
    bot_config_path = "./config/bot_config.json"
    with open(bot_config_path) as data_file:
        bot_config = json.load(data_file)

    api_key = bot_config['google_api_key']
    out_dir = '/home/pjdrm/PycharmProjects/LaMorocha/tango_db/'
    min_secs = 120
    max_secs = 210
    for query in QUERIES:
        if QUERY_YOUTUBE:
            videos = youtube_search(query, api_key, max_results=100)
            videos = add_video_len(videos)
            save_data(out_dir, query, videos)

        data_file_path = out_dir+query
        out_file_path = query+'.fil'
        filter_duration(data_file_path, min_secs, max_secs, out_dir, out_file_path)

        data_file_path += '.fil'
        out_file_path += '.nd'
        filter_duplicates(data_file_path, MAX_FUZZ_RATIO, out_dir, out_file_path)
    make_song_db('/home/pjdrm/PycharmProjects/LaMorocha/tango_db/',
                 '/home/pjdrm/PycharmProjects/LaMorocha/config/',
                 'music_db_v3.json')
    print('Done')