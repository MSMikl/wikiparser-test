import asyncio
import logging
import re

from urllib.parse import urlparse, urljoin

import aiohttp
import configargparse

from lxml import html

from worker import launch_workers


logger = logging.getLogger('parser')


async def follow_link(
        step: int,
        depth: int,
        target: str,
        url: str,
        base_url: str,
        previous_pages: list,
        viewed_pages: set,
        parsed_links: dict,
        tasks: asyncio.Queue,
        stop_flag: list,
    ):
    links = parsed_links.get(url)
    if links is None:
        links = await parse_page(url, base_url=base_url)
        logger.info(url)
        parsed_links[url] = links
    if target in links:
        stop_flag.append(1)
        previous_pages.append(url)
        return previous_pages
    if step == depth - 1:
        return
    new_viewed_pages = viewed_pages.copy()
    new_viewed_pages.update(*links)
    new_previous_pages = previous_pages.copy()
    new_previous_pages.append(url)
    for link in links:
        if link in viewed_pages:
            continue
        await tasks.put(follow_link(
            step + 1,
            depth,
            target,
            link,
            base_url,
            new_previous_pages,
            new_viewed_pages,
            parsed_links,
            tasks,
            stop_flag,
        ))
        viewed_pages.add(link)


async def parse_page(url, base_url):
    async with aiohttp.ClientSession() as session:
        response = await session.get(url)
        text = await response.text()
    tree = html.fromstring(text).xpath('//div[@id="bodyContent"]')[0]
    links = [link.get('href') for link in tree.xpath('.//a[starts-with(@href, "/wiki")]')]
    html_links = [not link.endswith(".svg") and link for link in links]
    return [urljoin(base_url, link) for link in html_links]


async def find_path(url, target, depth=3):
    parsed_url = urlparse(url)
    base_url = parsed_url.scheme + '://' + parsed_url.netloc
    tasks = asyncio.Queue()
    result = []
    workers = 20
    stop_flag = []
    parsed_links = {}
    await tasks.put(follow_link(
        step=0,
        depth=depth,
        target=target,
        url=url,
        base_url=base_url,
        previous_pages=list(),
        viewed_pages=set(),
        parsed_links=parsed_links,
        tasks=tasks,
        stop_flag=stop_flag,
    ))
    await launch_workers(tasks, result, workers, stop_flag)
    while not tasks.empty():
        task = await tasks.get()
        task.close()
    result[0].append(target)
    return result[0]


async def get_text_from_page(url, link):
    async with aiohttp.ClientSession() as session:
        response = await session.get(url)
        text = await response.text()
    tree = html.fromstring(text)
    rel_link = urlparse(link).path
    block = tree.xpath(f'//*[a/@href="{rel_link}"]')[0]
    link_text = block.xpath(f'./a[@href="{rel_link}"]')[0].text
    sentences = re.split("[.!?] ", block.text_content())
    for sentence in sentences:
        if sentence.find(link_text) >= 0:
            return sentence.strip()


async def main():
    logger.addHandler(logging.FileHandler('logs.txt', mode='w'))
    logger.setLevel(logging.INFO)

    
    arg_parser = configargparse.ArgParser(default_config_files=['./config.ini'])
    arg_parser.add('-s', '--start', required=True, help='Start URL') 
    arg_parser.add('-t', '--target', required=True, help='Target URL')
    arg_parser.add('-d', '--depth', help='Search depth')

    options = arg_parser.parse_args()

    url = options.start
    target = options.target
    depth = int(options.depth)
    path = await find_path(url, target, depth)
    for number, step in enumerate(path[1:], 1):
        sentence = await get_text_from_page(url, step)
        print("\n")
        print(f"{number}----------")
        print(sentence)
        print(step)
        url = step
    print("\n")


if __name__ == '__main__':
    asyncio.run(main())
