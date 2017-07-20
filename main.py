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

# Get the plugin url in plugin:// notation.
_url = sys.argv[0]
# Get the plugin handle as an integer number.
_handle = int(sys.argv[1])

HOME_PAGE = 'https://gostream.is'

def get_url(**kwargs):
    """
    Create a URL for calling the plugin recursively from the given set of keyword arguments.

    :param kwargs: "argument=value" pairs
    :type kwargs: dict
    :return: plugin call URL
    :rtype: str
    """
    return '{0}?{1}'.format(_url, urlencode(kwargs))


def get_categories():
    """
    Get the list of video categories.

    Here you can insert some parsing code that retrieves
    the list of video categories (e.g. 'Movies', 'TV-shows', 'Documentaries' etc.)
    from some site or server.

    .. note:: Consider using `generator functions <https://wiki.python.org/moin/Generators>`_
    instead of returning lists.

    :return: The list of video categories
    :rtype: list
    """
    headers = {'User-Agent': 'Fake'}
    req = urllib2.Request(HOME_PAGE, None, headers)
    home = urllib2.urlopen(req)
    bs = BeautifulSoup(home.read(), 'html.parser')
    cat = []
    for a in bs.find_all('a'):
        try:
            if '/genre/' in a['href'] and 'title' not in a.attrs:
                url = a['href'].split('/')[-2].lower().replace(' ', '-') + '/'
                cat.append({'name':a.text,'url':url})
        except KeyError:
            pass

    cat.append({'name':'Search', 'url':'search'})
    return cat

def get_videos(category):
    """
    Get the list of videofiles/streams.

    Here you can insert some parsing code that retrieves
    the list of video streams in the given category from some site or server.

    .. note:: Consider using `generators functions <https://wiki.python.org/moin/Generators>`_
    instead of returning lists.

    :param category: Category name
    :type category: str
    :return: the list of videos in the category
    :rtype: list
    """
    if category == 'search':
        kb = xbmc.Keyboard('', 'Please enter the video title')
        kb.doModal()
        if not kb.isConfirmed():
            vid = []
        query = kb.getText().replace(' ', '+')
        url = HOME_PAGE + '/movie/search/' + query
    else:
        url = HOME_PAGE + '/genre/' + category

    headers = {'User-Agent': 'Fake'}
    req = urllib2.Request(url, None, headers)
    page = urllib2.urlopen(req).read()
    bs = BeautifulSoup(page, 'html.parser')
    vid = []
    for a in bs.find_all('div', class_="movies-list movies-list-full")[0].find_all('a'):
        quality = a.find('span', class_='mli-quality')
        thumb  = a.img['data-original']
        mid = a['data-url'].split('/')[-1]
        name = a['title']+' ['+quality.string+']' if quality else a['title']

        vid.append({'mid':mid, 'thumb':thumb, 'name':name, 'fanart':thumb.replace('/poster/','/cover/')})

    # next page
    n = bs.find('a', rel='next')
    if n is not None:
        vid.append({'name':'Next', 'url':'/'+'/'.join(n['href'].split('/')[-2:])})
    return vid

def list_categories():
    """
    Create the list of video categories in the Kodi interface.
    """
    # Get video categories
    categories = get_categories()
    # Iterate through categories
    for category in categories:
        list_item = xbmcgui.ListItem(label=category['name'])
        list_item.setInfo('video', {'title': category['name'], 'genre': category['name']})
        # Create a URL for a plugin recursive call.
        # Example: plugin://plugin.video.example/?action=listing&category=Animals
        url = get_url(action='listing', category=category['url'])
        # is_folder = True means that this item opens a sub-list of lower level items.
        is_folder = True
        # Add our item to the Kodi virtual folder listing.
        xbmcplugin.addDirectoryItem(_handle, url, list_item, is_folder)
    # Add a sort method for the virtual folder items (alphabetically, ignore articles)
    #xbmcplugin.addSortMethod(_handle, xbmcplugin.SORT_METHOD_LABEL_IGNORE_THE)
    # Finish creating a virtual folder.
    xbmcplugin.endOfDirectory(_handle)


def list_videos(category):
    """
    Create the list of playable videos in the Kodi interface.

    :param category: Category name
    :type category: str
    """
    # Get the list of videos in the category.
    videos = get_videos(category)
    # Iterate through videos.
    for video in videos:
        if 'mid' not in video:
            # for next page
            list_item = xbmcgui.ListItem(label=video['name'])
            list_item.setInfo('video', {'title': video['name']})
            is_folder = True
            url = get_url(action='listing', category=video['url'])
        else:
            list_item = xbmcgui.ListItem(label=video['name'])
            list_item.setInfo('video', {'title': video['name']})
            list_item.setArt({'thumb': video['thumb'], 'fanart':video['fanart'], 'icon': video['thumb']})
            list_item.setProperty('IsPlayable', 'true')
            # Create a URL for a plugin recursive call.
            # Example: plugin://plugin.video.example/?action=play&video=http://www.vidsplay.com/wp-content/uploads/2017/04/crab.mp4
            url = get_url(action='play', video=video['mid'])
            is_folder = False
        xbmcplugin.addDirectoryItem(_handle, url, list_item, is_folder)
    # Finish creating a virtual folder.
    xbmcplugin.endOfDirectory(_handle)


def play_video(mid):
    """
    Play a video by the provided path.

    :param path: Fully-qualified video URL
    :type path: str
    """
    # get url
    headers = {'User-Agent': 'Fake'}
    url = HOME_PAGE+'/ajax/movie_episodes/'+mid
    req = urllib2.Request(url, None, headers)
    ajax = urllib2.urlopen(req)
    res = json.loads(ajax.read())
    bs = BeautifulSoup(res['html'], 'html.parser')
    a = bs.find_all('a')
    data_id = a[0]['data-id']

    url = HOME_PAGE+'/ajax/movie_token?eid=%s&mid=%s' % (data_id, mid)
    req = urllib2.Request(url, None, headers)
    ajax = urllib2.urlopen(req).read()
    ajax = ajax.replace(', ','&').replace('_','').replace(';','').replace("'", '')
    url = HOME_PAGE+'/ajax/movie_sources/%s?%s' % (data_id, ajax)
    req = urllib2.Request(url, None, headers)
    ajax = urllib2.urlopen(req).read()
    res = json.loads(ajax)
    try:
        url = res['playlist'][0]['sources'][0]['file']
    except TypeError:
        url = ''
    # Create a playable item with a path to play.
    play_item = xbmcgui.ListItem(path=url)
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
            # Display the list of videos in a provided category.
            list_videos(params['category'])
        elif params['action'] == 'play':
            # Play a video from a provided URL.
            play_video(params['video'])
        else:
            # If the provided paramstring does not contain a supported action
            # we raise an exception. This helps to catch coding errors,
            # e.g. typos in action names.
            raise ValueError('Invalid paramstring: {0}!'.format(paramstring))
    else:
        # If the plugin is called from Kodi UI without any parameters,
        # display the list of video categories
        list_categories()


if __name__ == '__main__':
    # Call the router function and pass the plugin call parameters to it.
    # We use string slicing to trim the leading '?' from the plugin call paramstring
    router(sys.argv[2][1:])
