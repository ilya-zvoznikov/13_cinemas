from bs4 import BeautifulSoup
import requests
import logging
from fake_useragent import UserAgent
import sys

AFISHA_URL = 'https://www.afisha.ru/novosibirsk/schedule_cinema/'
KINOPOISK_URL = 'https://www.kinopoisk.ru/index.php?kp_query={}&what='


def getCinemasLogger():
    logging.basicConfig(
        filename='cinemas.log',
        level=logging.DEBUG,
        filemode='w',
        format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
    )
    cinemasLogger = logging.getLogger('CinemasLogger')
    return cinemasLogger


def get_proxies_list():
    response = requests.get(
        'http://www.freeproxy-list.ru/api/proxy?anonymity=false&token=demo',
    )
    return response.text.split('\n')


def fetch_page(url, user_agent, proxy=None):
    try:
        response = requests.get(
            url,
            headers={'User-Agent': user_agent},
            proxies={'https': proxy},
            timeout=30,
        )
        return response.text
    except (
            requests.exceptions.ConnectionError,
            requests.exceptions.ConnectTimeout,
    ):
        return


def parse_afisha_list(raw_html):
    movies_list = []
    soup = BeautifulSoup(raw_html, 'html.parser')
    widget_content = soup.find('div', {'id': 'widget-content'})
    ul = widget_content.div.div.div.ul
    for li in ul.find_all('li'):
        movies_list.append(li.section.h3.a.text)
    return movies_list


def fetch_movie_rating(raw_html):
    soup = BeautifulSoup(raw_html, 'html.parser')
    block_left_pad = soup.find('td', {'id': 'block_left_pad'})
    element_most_wanted = block_left_pad.find(
        'div',
        {'class': 'element most_wanted'},
    )
    try:
        movie_rating = element_most_wanted.find(
            'div',
            {'class': 'rating'},
        ).text
    except AttributeError as e:
        logger.error(e)
        return
    if not movie_rating:
        return
    return movie_rating


def output_movies_to_console(movies):
    for movie in sorted(movies, key=lambda m: m['rating'], reverse=True):
        if movie['rating'] == 0:
            rating = 'Рейтинг недоступен (мало оценок)'
        else:
            rating = movie['rating']
        print('{} / {}'.format(movie['name'], rating))


if __name__ == '__main__':
    logger = getCinemasLogger()
    logger.info('Script started')
    user_agent = UserAgent()
    afisha_raw_html = fetch_page(AFISHA_URL, user_agent.random)
    if not afisha_raw_html:
        message = 'No info at Afisha.ru or connection error'
        logger.error('Script finished with "{}"'.format(message))
        sys.exit(message)
    else:
        logger.info("Afisha's content loaded")

    movies_names_list = parse_afisha_list(afisha_raw_html)
    if not movies_names_list:
        message = 'No movies today'
        logger.error('Script finished with "{}"'.format(message))
        sys.exit(message)
    else:
        logger.info('Movies names list fetched')
    movies = [{'name': i} for i in movies_names_list]
    for movie in movies:
        kinopoisk_raw_html = fetch_page(
            KINOPOISK_URL.format(movie['name']),
            user_agent.random,
        )
        if not kinopoisk_raw_html:
            logger.error('Error page "{}" fetching'.format(movie['name']))
            continue
        else:
            logger.info('Page "{}" fetched'.format(movie['name']))
        movie_rating = fetch_movie_rating(kinopoisk_raw_html)
        if not movie_rating:
            logger.error("Error {}'s rating fetching".format(movie['name']))
            movie_rating = 0
        else:
            logger.info('Movie "{}" rating fetched'.format(movie['name']))
        movie['rating'] = float(movie_rating)
    output_movies_to_console(movies)
    logger.info('Script finished')
