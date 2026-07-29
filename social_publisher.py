# social_publisher.py
import requests
import time

def post_to_twitter_thread(tweets_list, bearer_token):
    """
    Takes a list of tweets and posts them as a thread using Twitter v2 API.
    tweets_list: list of strings (e.g., ["Tweet 1", "Tweet 2"])
    """
    url = "https://api.twitter.com/2/tweets"
    headers = {
        "Authorization": f"Bearer {bearer_token}",
        "Content-Type": "application/json"
    }
    
    previous_tweet_id = None
    successful_tweets = 0
    
    for tweet in tweets_list:
        payload = {"text": tweet}
        if previous_tweet_id:
            payload["reply"] = {"in_reply_to_tweet_id": previous_tweet_id}
            
        try:
            response = requests.post(url, json=payload, headers=headers)
            if response.status_code == 201:
                previous_tweet_id = response.json()['data']['id']
                successful_tweets += 1
                time.sleep(1) # API rate limit se bachne ke liye 1 sec delay
            else:
                return False, f"Twitter API Error: {response.text}"
        except Exception as e:
            return False, f"System Error: {str(e)}"
            
    return True, f"Success! {successful_tweets} tweets posted in thread."

def post_to_linkedin(post_text, access_token, person_urn):
    """
    Posts text to LinkedIn using v2 API.
    person_urn: User's LinkedIn ID (e.g., 'urn:li:person:12345ABC')
    """
    url = "https://api.linkedin.com/v2/ugcPosts"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "X-Restli-Protocol-Version": "2.0.0"
    }
    
    payload = {
        "author": person_urn,
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {
                    "text": post_text
                },
                "shareMediaCategory": "NONE"
            }
        },
        "visibility": {
            "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
        }
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code == 201:
            return True, "Successfully posted to LinkedIn!"
        else:
            return False, f"LinkedIn API Error: {response.text}"
    except Exception as e:
        return False, f"System Error: {str(e)}"