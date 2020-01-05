from apiclient.discovery import build
import json
import pafy
from tqdm import tqdm

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


def save_data(out_dir, out_file_path, data):
    with open(out_dir+out_file_path, 'w+') as outfile:
        outfile.write(json.dumps(data, indent=4))


if __name__ == "__main__":
    bot_config_path = "./config/bot_config.json"
    with open(bot_config_path) as data_file:
        bot_config = json.load(data_file)

    api_key = bot_config['google_api_key']
    out_dir = '/home/pjdrm/PycharmProjects/LaMorocha/tango_db/'
    query = "Carlos Di Sarli"
    videos = youtube_search(query, api_key, max_results=100)
    videos = add_video_len(videos)
    save_data(out_dir, query, videos)
    print('Done')