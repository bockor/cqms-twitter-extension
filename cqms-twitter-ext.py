#!/usr/bin/python3

'''


Author:             bruno.on.the.road@gmaol.com

Version:            0.6.0

Date:               27 Jun 2019

Platform:			Ubuntu Server 18.04 LTS

python version:     3.4.3

tweepy version:     3.6.0

Requires:			A log file formatted as:
                    
                    match: (Housing|Fast line|Room)
                    qwin_event.trig(9,1,%221|4|5||F|46|1|0|6|Fast line||R|90|1|0|4|Room 110 A||R|89|1|0|4|Room 110 A||R|88|1|0|4|Room 110 A||F|45|1|0|6|Fast line|%22);
                    qwin_event.trig(9,1,%221|4|5||F|46|1|0|6|Fast line||F|46|1|0|6|Fast line||R|90|1|0|4|Room 110 A||R|89|1|0|4|Room 110 A||R|88|1|0|4|Room 110 A|%22);
                    qwin_event.trig(9,1,%221|4|5||F|47|1|0|6|Fast line||F|46|1|0|6|Fast line||F|46|1|0|6|Fast line||R|90|1|0|4|Room 110 A||R|89|1|0|4|Room 110 A|%22);
                    qwin_event.trig(9,1,%221|4|5||F|48|1|0|6|Fast line||F|47|1|0|6|Fast line||F|46|1|0|6|Fast line||F|46|1|0|6|Fast line||R|90|1|0|4|Room 110 A|%22);
                    qwin_event.trig(9,1,%221|4|5||F|49|1|0|6|Fast line||F|48|1|0|6|Fast line||F|47|1|0|6|Fast line||F|46|1|0|6|Fast line||F|46|1|0|6|Fast line|%22);
                    qwin_event.trig(9,1,%221|4|5||H|26|1|0|8|Housing||F|49|1|0|6|Fast line||F|48|1|0|6|Fast line||F|47|1|0|6|Fast line||F|46|1|0|6|Fast line|%22);
                    qwin_event.trig(9,1,%221|4|5||R|91|0|1|3|Room 110 B/C||H|26|1|0|8|Housing||F|49|1|0|6|Fast line||F|48|1|0|6|Fast line||F|47|1|0|6|Fast line|%22);
                    qwin_event.trig(9,1,%221|4|5||R|92|0|1|3|Room 110 B/C||R|91|0|1|3|Room 110 B/C||H|26|1|0|8|Housing||F|49|1|0|6|Fast line||F|48|1|0|6|Fast line|%22);
                    qwin_event.trig(9,1,%221|4|5||F|50|1|0|6|Fast line||R|92|0|1|3|Room 110 B/C||R|91|0|1|3|Room 110 B/C||H|26|1|0|8|Housing||F|49|1|0|6|Fast line|%22);
                    ... 
                    qwin_event.trig(9,1,%221|4|5||F|51|1|0|6|Fast line||F|50|1|0|6|Fast line||R|92|0|1|3|Room 110 B/C||R|91|0|1|3|Room 110 B/C||H|26|1|0|8|Housing|%22);

                    We obtain and filter these entries by picking up the information between the Qmatic ticketing machine(s) and one of the waiting room smart monitors. 
                    A Mikrotik device port mirrors the relevant packets and we capture these by executing the  cqms-twitter script.  The script looks like: 

                    sudo ngrep -d eno1 '(Housing|Fast line|Room|Road Tax)' -W byline -l tcp port 80 | 
                        grep -E --line-buffered 'Housing|Fast line|Room|Road Tax' | 
                        tee cqms-messages.log

                    We might consider the below command to work in the background and append entries to the file iso truncating the file:

                    sudo ngrep -d eno1 '(Housing|Fast line|Room|Road Tax)' -W byline -l tcp port 80 |
                        grep -E --line-buffered 'Housing|Fast line|Room|Road Tax' |
                        tee -a cqms-messages.log > /dev/null

Scheduler:          This script needs to be executed repeatedly.  We use the Linux crontab command to achieve this goal.  The crontab command creates a crontab file
                    containing commands and instructions for the cron daemon to execute.  In the below example the script is executed every 5 minutes.

                    crontab -l --> causes the current crontab to be displayed on standard output. 

                    */5 * * * * /home/csu-admin/cqms/cqms-twitter-ext.py >> /home/csu-admin/cqms/cqms-twitter-ext.log 2>&1

                    crontab -e --> used to edit the current crontab using the default editor

                    The production crontab definition is depicted in the cqms-cronjobs file. 

System Time:		In order to succesfully send updates to the Twtter timeline an exact System Time is paramount. 

Notes:				- Building 210 Counters:
						Fast line
						Housing
						Road Tax
						Room 110A
						Room 110B/C
						Room 109D/E
						Room 109F
						Room 111
						VAT
'''

#initialisation: load all required modules/files
import sys
import tweepy
import threading
import time
import datetime
from random import randint,choice
from credentials import *
from shape_holidays import holidays

#initialisation: initialise a bunch of variables

#queue status messages from ticketing machine to monitor are picked up by our packet sniffer
qmatic_msg="/home/csu-admin/cqms/cqms-messages.log"

 # emoji characters reference: http://www.unicode.org/emoji/charts/full-emoji-list.html
EMOJI_UP = "\U0001F199"
EMOJI_RUN = "\U0001F3C3"
EMOJI_SICK = "\U0001F915"
EMOJI_FROWNING = "\u2639"

#I believe this one is obvious
maintenance_txt ='''
{EMO} This beloved channel is currently under maintenance.
We regret for eventual inconvenience.
Have a golden day!
'''.format(EMO=EMOJI_SICK)

#I believe this one is obvious
closed_txt ='''
{EMO} Sorry folks, we are closed.

Hours of operation:

MONDAY- THURSDAY
    0845 - 1300
    1400 - 1700

FRIDAY
    0845 - 1300
'''.format(EMO=EMOJI_FROWNING)

#we still have space to post an additional message to the tweet
snappy_msg = [
'DO NOT MISS YOUR TURN!',
'BE BACK ON TIME!',
'ENSURE YOU BRING ALL DOCUMENTATION AND CERTIFICATES',
'DO NOT LOSE YOUR TICKET',
'NEWCOMERS PLEASE CHECKOUT https://www.shape2day.com/arriving--leaving-shape/inprocessing',
'NEVER LEAVE YOUR PET IN A HOT CAR!'
]


#========================== FUNCTIONS ================================#

def do_open():
    if not verify_holiday():
        api = do_authenticate()
        batch_destroy(api)
        post_new_tweet(api, format_new_tweet(format_last_log_line()))
    else:
        #no Twitter timeline updates required on a SHAPE holiday, so quit on the spot!
        sys.exit(55)    

def do_closed():
    api = do_authenticate()
    batch_destroy(api)
    post_new_tweet(api, closed_txt)     

def do_maint():
    api = do_authenticate()
    batch_destroy(api)
    post_new_tweet(api, maintenance_txt)

def do_action_unknown():
    print ('Unknown action', sys.argv[1], ', I can only handle \'open\',\'closed\', and \'maint\'' )

def verify_holiday():
    # create a date instance for today and cast it to a str obj
    this_day = datetime.date.today().strftime('%d/%m/%Y')
    #Is 'this_day' included in the holidays list ?
    if this_day in holidays:
        return True
    else:
        return False    

def do_authenticate():
    #OAuth process using keys and tokens from the credentials file
    auth = tweepy.OAuthHandler(consumer_key, consumer_secret)    
    auth.set_access_token(access_token, access_token_secret)
    #creation of the actual interface using authentication
    api = tweepy.API(auth)
    #print(api.me().screen_name) # prints ChannelBruno
    #print ("Authenticated as: %s" % api.me().screen_name) 
    return api

def delete_thread(api, objectId):
    '''
    docstring here
    '''
    try:
        api.destroy_status(objectId)
        #print ("Deleted:", objectId)
    except:
        print ("Failed to delete:", objectId)

def batch_destroy(api):
    '''
    docstring here
    '''
    threads = []
    for status in tweepy.Cursor(api.user_timeline).items():
        try:
            t = threading.Thread(target=delete_thread,args=(api,status.id, ))
            threads.append(t)
            t.start()
        except:
            pass
            #print ("Failed to delete:", status.id)


def format_last_log_line():
    '''
    Read, analyse and format last qmatic ticketing machine message
    '''
    try:
        with open (qmatic_msg, 'r') as f:
            #read last line here
            last_ngrep_match = f.readlines()[-1]
            last_ngrep_match_split = last_ngrep_match.split('|')
    #'''
    #except FileNotFoundError:
    #    print ("No such file ", qmatic_msg)
    #    sys.exit(11)
    #'''    
    except IOError:
        print ("could not read file: ", qmatic_msg)
        sys.exit(10)

    '''
    # Or use a simulator
    last_ngrep_match_split = [str(randint(1,99)) for _ in range(40)]
    ''' 

    last_updates = [
	    {'counter':last_ngrep_match_split[9],
	    'series':last_ngrep_match_split[4],
	    'ticket':last_ngrep_match_split[5]},
	    {'counter':last_ngrep_match_split[16],
	    'series':last_ngrep_match_split[11],
	    'ticket':last_ngrep_match_split[12]},
	    {'counter':last_ngrep_match_split[23],
	    'series':last_ngrep_match_split[18],
	    'ticket':last_ngrep_match_split[19]},
	    {'counter':last_ngrep_match_split[30],
	    'series':last_ngrep_match_split[25],
	    'ticket':last_ngrep_match_split[26]},
	    {'counter':last_ngrep_match_split[37],
	    'series':last_ngrep_match_split[32],
	     'ticket':last_ngrep_match_split[33]}
    ]
    return last_updates


def format_new_tweet(last_updates):
    '''
    docstring here
    '''
    tweet_txt = ""
    for last_update in last_updates:
        tweet_txt= tweet_txt \
        + last_update['series'] \
        + last_update['ticket'] \
        + " " + EMOJI_UP + " " \
        + last_update['counter'] \
        +"\n"

    tweet_txt = tweet_txt \
    + "\n" \
    + "Last update: " \
    + time.ctime() \
    + "\n" \
    + EMOJI_RUN + " " \
    + choice(snappy_msg)
    return tweet_txt


def post_new_tweet(api,tweet_txt):
    '''
    docstring here
    '''
    try:
        api.update_status(tweet_txt)
        #print("TWEET POSTED") 
    except tweepy.TweepError as e:
        print ("Error when sending tweet: {}".format(e.reason)) 


#=======================END OF FUNCTIONS =============================#    


if __name__ == "__main__":

    if len(sys.argv) == 2:
        '''
        execute the script with one of these arguments
            'cqms-twitter-ext.py open' for operation during business hours
            'cqms-twitter-ext.py closed' for operation outside business hours
            'cqms-twitter-ext.py maint' if system maintenance is planned
        '''
        actions= {
        'open' : do_open,
        'closed' : do_closed,
        'maint' : do_maint
        }

        #update timeline to Twitter Service
        actions.get(sys.argv[1], do_action_unknown)()
    else:
        print('I only handle ONE of these actions: \'open\',\'closed\' or \'maint\'')
