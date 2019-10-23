from bs4 import BeautifulSoup
import requests
import logging
from fake_useragent import UserAgent
import sys
from tqdm import tqdm

AFISHA_URL = 'https://www.afisha.ru/novosibirsk/schedule_cinema/'
AFISHA_PARAMS = {'view': 'list'}

KINOPOISK_URL = 'https://www.kinopoisk.ru{}'
KINOPOISK_PARAMS = {
    'level': '7',
    'from': 'forma',
    'result': 'adv',
    'm_act[from]': 'forma',
    'm_act[what]': 'content',
    'm_act[find]': '',
    'm_act[year]': '',
}


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
    proxies_list = response.text.split('\n') * 5
    proxies_list.insert(0, '')
    return proxies_list


def fetch_page(url, user_agent, proxies_list=('',), params=None):
    for proxy in proxies_list:
        try:
            response = requests.get(
                url,
                headers={'User-Agent': user_agent},
                params=params,
                proxies={'https': proxy},
                timeout=10,
            )
            if 'showcaptcha' in response.url:
                continue
            return response.text, response.url
        except (
                requests.exceptions.ConnectionError,
                requests.exceptions.ConnectTimeout,
                requests.exceptions.ReadTimeout,
        ):
            continue
    return


def parse_afisha_list(raw_html):
    movies_list = []
    soup = BeautifulSoup(raw_html, 'html.parser')
    for item_info in soup.find_all('div', {'class': 'new-list__item-info'}):
        movies_list.append(
            {
                'name': item_info.h3.text,
                'year': item_info.find(
                    'div', {'class': 'new-list__item-status'}
                ).text[:4],
            }
        )
    return movies_list


def fetch_movie_rating(raw_html, url):
    soup = BeautifulSoup(raw_html, 'html.parser')
    try:
        if 'index.php' in url:
            element_most_wanted = soup.find('div',
                                            {'class': 'element most_wanted'})
            movie_rating = float(element_most_wanted.div.div.text)
        else:
            block_rating = soup.find('div', {'id': 'block_rating'})
            movie_rating = float(block_rating.div.div.a.span.text)
    except (AttributeError, ValueError) as e:
        logger.error(e)
        return 0
    if not movie_rating:
        return 0
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
    proxies_list = get_proxies_list()
    afisha_raw_html, afisha_url = fetch_page(
        url=AFISHA_URL,
        user_agent=user_agent.random,
        params=AFISHA_PARAMS,
    )

    if not afisha_raw_html:
        message = 'No info at Afisha.ru or connection error'
        logger.error('Script finished with "{}"'.format(message))
        sys.exit(message)
    else:
        logger.info("Afisha's content loaded")

    movies = parse_afisha_list(afisha_raw_html)

    if not movies:
        message = 'No movies today'
        logger.error('Script finished with "{}"'.format(message))
        sys.exit(message)
    else:
        logger.info('Movies names list fetched')

    kinopoisk_urls_list = []
    progressbar = iter(tqdm(
        movies,
        desc='Getting movies info',
        leave=False,
    ))
    for movie in movies:
        next(progressbar)
        KINOPOISK_PARAMS['m_act[find]'] = movie['name']
        KINOPOISK_PARAMS['m_act[year]'] = movie['year']
        kinopoisk_raw_html, kinopoisk_movie_url = fetch_page(
            url=KINOPOISK_URL.format('/index.php'),
            user_agent=user_agent.random,
            proxies_list=proxies_list,
            params=KINOPOISK_PARAMS,
        )

        if not kinopoisk_raw_html:
            logger.error('Error page "{}" fetching'.format(movie['name']))
            continue
        else:
            logger.info('Page "{}" fetched'.format(movie['name']))
        movie['rating'] = fetch_movie_rating(
            kinopoisk_raw_html,
            kinopoisk_movie_url,
        )
        if not movie['rating']:
            logger.error(
                "Error {}'s rating fetching".format(movie['name']))
            movie_rating = 0
        else:
            logger.info('Movie "{}" rating fetched'.format(movie['name']))
    try:
        next(progressbar)
    except StopIteration:
        pass
    output_movies_to_console(movies)
    logger.info('Script finished')
