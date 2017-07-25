# -*- coding: utf-8 -*-
# Module: default
# Author: solsTiCe d'Hiver
# Created on: 2017-07-19
# License: GPL v.3 https://www.gnu.org/copyleft/gpl.html

import sys
from urllib import urlencode
import urllib2
from urlparse import parse_qsl
import xbmcgui
import xbmcplugin
from bs4 import BeautifulSoup
import json
import simplecache
import threading

_cache = simplecache.SimpleCache()
# Get the plugin url in plugin:// notation.
_url = sys.argv[0]
# Get the plugin handle as an integer number.
_handle = int(sys.argv[1])

APP_ID = 'plugin.video.gomovies'
HOME_PAGE = 'https://gostream.is'
UA = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Ubuntu Chromium/59.0.3071.109 Chrome/59.0.3071.109 Safari/537.36'
HEADERS = {'User-Agent': UA}

def get_url(**kwargs):
    """
    Create a URL for calling the plugin recursively from the given set of keyword arguments.

    :param kwargs: "argument=value" pairs
    :type kwargs: dict
    :return: plugin call URL
    :rtype: str
    """
    return '{0}?{1}'.format(_url, urlencode(kwargs))

def get_genres():
    """
    Get the list of video genres.

    :return: The list of video genres
    :rtype: list
    """
    req = urllib2.Request(HOME_PAGE, None, HEADERS)
    home = urllib2.urlopen(req)
    bs = BeautifulSoup(home.read(), 'html.parser')
    cat = []
    for a in bs.find_all('a'):
        try:
            if '/genre/' in a['href'] and 'title' not in a.attrs:
                url = a['href'].replace(HOME_PAGE, '')
                cat.append({'name':a.text,'url':url})
        except KeyError:
            pass

    cat.append({'name':'Series', 'url':'series'})
    cat.append({'name':'Search', 'url':'search'})
    return cat

def list_genres():
    """
    Create the list of video genres in the Kodi interface.
    """
    # Get video genres
    genres = get_genres()
    # Iterate through genres
    for genre in genres:
        list_item = xbmcgui.ListItem(label=genre['name'])
        list_item.setInfo('video', {'title': genre['name']})
        # Create a URL for a plugin recursive call.
        # Example: plugin://plugin.video.example/?action=listing&genre=Animals
        url = get_url(action='listing', genre=genre['url'])
        is_folder = True
        # Add our item to the Kodi virtual folder listing.
        xbmcplugin.addDirectoryItem(_handle, url, list_item, is_folder)
    # Finish creating a virtual folder.
    xbmcplugin.endOfDirectory(_handle)

def get_plot(data_url, vid):
    req = urllib2.Request(data_url, None, HEADERS)
    ajax = urllib2.urlopen(req).read()
    p = BeautifulSoup(ajax, 'html.parser', from_encoding='utf-8')
    vid['plot'] = p.find(class_='f-desc').string

def get_videos(genre):
    """
    Get the list of videofiles/streams.

    :param genre: Genre name
    :type genre: str
    :return: the list of videos in the genre
    :rtype: list
    """
    if genre == 'search':
        kb = xbmc.Keyboard('', 'Please enter your search')
        kb.doModal()
        if not kb.isConfirmed():
            vid = []
            return vid
        query = kb.getText().replace(' ', '+')
        url = HOME_PAGE + '/movie/search/' + query
    elif genre == 'series':
        url = HOME_PAGE + '/movie/filter/series'
    else:
        url = HOME_PAGE + genre

    req = urllib2.Request(url, None, HEADERS)
    page = urllib2.urlopen(req).read()
    bs = BeautifulSoup(page, 'html.parser')
    vid = []
    indx = 0
    threads = []
    for a in bs.find('div', class_="movies-list movies-list-full").find_all('a'):
        quality = a.find('span', class_='mli-quality')
        thumb  = a.img['data-original']
        mid = a['data-url'].split('/')[-1]
        name = a['title']+' ['+quality.string+']' if quality else a['title']
        # try the cache
        data = _cache.get('%s.%s' % (APP_ID, mid))
        if data:
            vid.append({'name':data['name'], 'mid':mid, 'thumb':data['thumb'], 'fanart':data['fanart'],
                'plot':data['plot']})
        else:
            vid.append({'name':name, 'mid':mid, 'thumb':thumb, 'fanart':thumb.replace('/poster/','/cover/')})
            # ajax call for the plot
            t = threading.Thread(target=get_plot, args=(a['data-url'], vid[indx]))
            threads.append((t, indx))
            t.start()
        indx += 1

    for t,i in threads:
        t.join()
        # cache data
        data = {'name':vid[i]['name'], 'thumb': vid[i]['thumb'], 'fanart':vid[i]['fanart'], 'plot':vid[i]['plot']}
        _cache.set('%s.%s' % (APP_ID, vid[i]['mid']), data)

    # next page
    n = bs.find('a', rel='next')
    if n is not None:
        vid.append({'name':'Next', 'url':n['href'].replace(HOME_PAGE, '')})
    return vid

def list_videos(genre):
    """
    Create the list of playable videos in the Kodi interface.

    :param genre: Category name
    :type genre: str
    """
    # Get the list of videos in the genre.
    videos = get_videos(genre)
    # Iterate through videos.
    for video in videos:
        list_item = xbmcgui.ListItem(label=video['name'])
        is_folder = True
        if 'mid' not in video:
            # for next page
            list_item.setInfo('video', {'title': video['name']})
            url = get_url(action='listing', genre=video['url'])
        else:
            list_item.setInfo('video', {'title': video['name'], 'plot':video['plot']})
            list_item.setArt({'thumb': video['thumb'], 'fanart':video['fanart'], 'icon': video['thumb']})
            # Create a URL for a plugin recursive call.
            # Example: plugin://plugin.video.example/?action=play&video=21234
            url = get_url(action='listing', video=video['mid'])
        xbmcplugin.addDirectoryItem(_handle, url, list_item, is_folder)
    # Finish creating a virtual folder.
    xbmcplugin.endOfDirectory(_handle)

def get_links(mid):
    # gather id of each link for each server
    url = HOME_PAGE+'/ajax/movie_episodes/'+mid
    req = urllib2.Request(url, None, HEADERS)
    ajax = urllib2.urlopen(req)
    res = json.loads(ajax.read())
    bs = BeautifulSoup(res['html'], 'html.parser')
    length = len(bs.find(class_='les-content').find_all('a'))
    videolink = [None]*length
    for div in bs.find_all(class_='les-content'):
        for a in div.find_all('a'):
            data_id = a['data-id']
            indx = int(a['data-index'])
            if videolink[indx] is None:
                videolink[indx] = {'ids':[]}
            videolink[indx]['name'] = a['title']
            videolink[indx]['ids'].append(data_id)
    return videolink

def list_links(mid):
    videolink = get_links(mid)
    for v in videolink:
        list_item = xbmcgui.ListItem(label=v['name'])
        list_item.setInfo('video', {'title': v['name']})
        list_item.setProperty('IsPlayable', 'true')
        # Create a URL for a plugin recursive call.
        # Example: plugin://plugin.video.example/?action=play&ids=64534%2C65345&mid=21704
        url = get_url(action='play', ids=','.join(v['ids']), mid=mid, name=v['name'])
        is_folder = False
        xbmcplugin.addDirectoryItem(_handle, url, list_item, is_folder)
    # Finish creating a virtual folder.
    xbmcplugin.endOfDirectory(_handle)

def play_video(ids, mid, name):
    """
    Try to play a video of mid id in the set of ids

    :param ids: List of ids on servers (string)
    :param mid: Id of the video
    """
    ids = ids.split(',') # turn it into a list
    play_item = xbmcgui.ListItem()
    for data_id in ids:
        url = HOME_PAGE+'/ajax/movie_token?eid=%s&mid=%s' % (data_id, mid)
        req = urllib2.Request(url, None, HEADERS)
        ajax = urllib2.urlopen(req).read()
        ajax = ajax.replace(', ','&').replace('_','').replace(';','').replace("'", '')
        url = HOME_PAGE+'/ajax/movie_sources/%s?%s' % (data_id, ajax)
        try:
            req = urllib2.Request(url, None, HEADERS)
            ajax = urllib2.urlopen(req).read()
            res = json.loads(ajax)
            playlist = res['playlist'][0]
            path = playlist['sources'][0]['file']
            # try to open it
            req = urllib2.Request(path, None, HEADERS)
            video = urllib2.urlopen(req)
            video.close()
            # Create a playable item with a path to play.
            play_item.setPath('%s|User-Agent=%s&Referer=%s' % (path, UA, HOME_PAGE))
            mtype = playlist['sources'][0]['type']
            if mtype == 'mp4': mtype = 'video/mp4'
            play_item.setMimeType(mtype)
            sub = []
            for s in playlist['tracks']:
                sub.append(s['file'])
            play_item.setSubtitles(sub)
            # if we're here then all is good. Abort the loop
            break
        except urllib2.HTTPError:
            continue
    data = _cache.get('%s.%s' % (APP_ID, mid))
    if data:
        play_item.setInfo('video', {'title': data['name']+' - '+name, 'plot':data['plot']})
        play_item.setArt({'thumb': data['thumb'], 'fanart':data['fanart'], 'icon': data['thumb']})
    # Pass the item to the Kodi player.
    xbmcplugin.setResolvedUrl(_handle, True, listitem=play_item)

def router(paramstring):
    """
    Router function that calls other functions
    depending on the provided paramstring

    :param paramstring: URL encoded plugin paramstring
    :type paramstring: str
    """
    # Parse a URL-encoded paramstring to the dictionary of
    # {<parameter>: <value>} elements
    params = dict(parse_qsl(paramstring))
    # Check the parameters passed to the plugin
    if params:
        if params['action'] == 'listing':
            # Display the list of videos in a provided genre.
            if 'genre' in params:
                list_videos(params['genre'])
            elif 'video' in params:
                list_links(params['video'])
        elif params['action'] == 'play':
            # Play a video from a provided URL.
            play_video(params['ids'], params['mid'], params['name'])
        else:
            # If the provided paramstring does not contain a supported action
            # we raise an exception. This helps to catch coding errors,
            # e.g. typos in action names.
            raise ValueError('Invalid paramstring: {0}!'.format(paramstring))
    else:
        # If the plugin is called from Kodi UI without any parameters,
        # display the list of video genres
        list_genres()


if __name__ == '__main__':
    # Call the router function and pass the plugin call parameters to it.
    # We use string slicing to trim the leading '?' from the plugin call paramstring
    router(sys.argv[2][1:])
