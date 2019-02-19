from pyquery import PyQuery as pq
from .constants import DATA_TYPE, HEADERS, SERIES_ENDPOINTS, SERIES_CN_ENDPOINTS, ENDPOINTS, REVERSE_ENDPOINTS, \
    SINGLE_PAGE_ENDPOINTS, SERIES_STORY_ENDPOINTS, REPORT_ENDPOINTS, COLLECTION_ENDPOINTS, \
    REVERSE_COLLECTION_ENDPOINTS, DB_NAME, URL_PARAMS
from ..items import *
from .parse import parse_html
import sqlite3


def get_type_by_url(url):
    if url in SERIES_ENDPOINTS:
        return DATA_TYPE['scp-series']
    elif url in SERIES_CN_ENDPOINTS:
        return DATA_TYPE['scp-series-cn']
    elif url in SINGLE_PAGE_ENDPOINTS:
        return DATA_TYPE['single-page']
    elif url in SERIES_STORY_ENDPOINTS:
        return DATA_TYPE['series-archive']
    elif url in REPORT_ENDPOINTS:
        return DATA_TYPE['reports-interviews-and-logs']
    elif url in ENDPOINTS.values():
        return DATA_TYPE[REVERSE_ENDPOINTS[url]]
    elif url in COLLECTION_ENDPOINTS.values():
        return DATA_TYPE[REVERSE_COLLECTION_ENDPOINTS[url]]
    else:
        return -1


def get_empty_link_for_detail():
    con = sqlite3.connect(DB_NAME)
    cur = con.cursor()
    cur.execute('select link from scps where detail is NULL;')
    link_list = [t[0] for t in cur]
    cur.execute('select link from scp_collection where detail is NULL;')
    link_list = link_list + [t[0] for t in cur]
    con.close()
    return link_list


def get_404_link_for_detail():
    con = sqlite3.connect(DB_NAME)
    cur = con.cursor()
    cur.execute('select link from scps where not_found = 1;')
    link_list = [t[0] for t in cur]
    con.close()
    return link_list


def get_all_link_by_download_type(download_type):
    con = sqlite3.connect(DB_NAME)
    cur = con.cursor()
    cur.execute('select link from scps where download_type = ' + str(download_type) + ';')
    link_list = [t[0] for t in cur]
    con.close()
    return link_list
    # return ['/scp-cn-1000']


class ScpListSpider(scrapy.Spider):  # 需要继承scrapy.Spider类

    name = "main_list_spider"  # 定义蜘蛛名
    allowed_domains = 'scp-wiki-cn.wikidot.com'

    item_list_urls = SERIES_ENDPOINTS + SERIES_CN_ENDPOINTS + list(ENDPOINTS.values()) + REPORT_ENDPOINTS
    collection_list_url = list(COLLECTION_ENDPOINTS.values()) \
                          + SERIES_STORY_ENDPOINTS

    start_urls = collection_list_url

    def parse(self, response):
        pq_doc = pq(response.body)
        item_list = parse_html(pq_doc, get_type_by_url(response.url))
        for info in item_list:
            yield info


class ScpSinglePageSpider(scrapy.Spider):
    """
    抓取单页面
    """
    name = "single_page_spider"
    allowed_domains = 'scp-wiki-cn.wikidot.com'
    start_urls = SINGLE_PAGE_ENDPOINTS

    def parse(self, response):
        pq_doc = pq(response.body)
        new_scp = ScpBaseItem(link=response.url[30:], title=pq_doc('div#page-title').text(),
                              scp_type=DATA_TYPE['single-page'])
        yield new_scp


class ScpDetailSpider(scrapy.Spider):
    name = 'detail_spider'
    allowed_domains = 'scp-wiki-cn.wikidot.com'
    start_urls = [('{_s_}://{_d_}' + link).format(**URL_PARAMS) for link in get_empty_link_for_detail()]
    handle_httpstatus_list = [404]  # 处理404页面，否则将会跳过

    def parse(self, response):
        if response.status != 404:
            detail_dom = response.css('div#page-content')[0]
            link = response.url[30:]
            if link == '/taboo':
                link = '/scp-4000'
            detail_item = ScpDetailItem(link=link,
                                        detail=detail_dom.extract().replace('  ', '').replace('\n', ''), not_found=0)
        else:
            detail_item = ScpDetailItem(link=response.url[30:], detail="<h3>抱歉，该页面尚无内容</h3>", not_found=1)
        yield detail_item


class ScpOffsetSpider(scrapy.Spider):
    name = 'offset_spider'
    allowed_domains = 'scp-wiki-cn.wikidot.com'
    start_urls = [('{_s_}://{_d_}' + link + '/offset/1').format(**URL_PARAMS) for link in
                  get_all_link_by_download_type(1)]
    handle_httpstatus_list = [404]  # 处理404页面，否则将会跳过

    def parse(self, response):
        dom = pq(response.body)
        if response.status != 404 and len(list(dom.find('#page-content .list-pages-box .list-pages-item'))) > 0:
            detail_dom = response.css('div#page-content')[0]
            offset_index = int(response.url.split('/')[-1])  # .../scp-xxx/offset/x
            link = response.url[30:]
            title = response.css('div#page-title')[0].css('::text').extract()[0].strip() + '-offset-' + str(offset_index)
            offset_item = ScpBaseItem(link=link, title=title, scp_type=DATA_TYPE['offset'],
                                      detail=detail_dom.extract().replace('  ', '').replace('\n', ''), not_found=0)
            yield offset_item
            offset_request = scrapy.Request(response.url[0:-1] + str(offset_index + 1), callback=parse_offset,
                                            headers=HEADERS, dont_filter=True)
            yield offset_request
        # yield detail_item


class ScpTagSpider(scrapy.Spider):  # 需要继承scrapy.Spider类

    name = "tag_spider"  # 定义蜘蛛名
    allowed_domains = 'scp-wiki-cn.wikidot.com'

    start_urls = [
        # tag
        'http://scp-wiki-cn.wikidot.com/system:page-tags/',
    ]

    def parse(self, response):
        pq_doc = pq(response.body)
        for a in pq_doc('div.pages-tag-cloud-box a').items():
            tag_name = a.text()
            link = a.attr('href')
            tag_request = scrapy.Request(response.urljoin(link), callback=parse_tag, headers=HEADERS)
            tag_request.meta['tag_name'] = tag_name
            yield tag_request


class ScpCollectionSpider(scrapy.Spider):  # 需要继承scrapy.Spider类

    name = "collection_spider"  # 定义蜘蛛名
    allowed_domains = 'scp-wiki-cn.wikidot.com'

    start_urls = [('{_s_}://{_d_}' + link ).format(**URL_PARAMS) for link in
                  get_all_link_by_download_type(4)]

    def parse(self, response):
        pq_doc = pq(response.body)
        for a in pq_doc('div.pages-tag-cloud-box a').items():
            tag_name = a.text()
            link = a.attr('href')
            tag_request = scrapy.Request(response.urljoin(link), callback=parse_tag, headers=HEADERS)
            tag_request.meta['tag_name'] = tag_name
            yield tag_request



def parse_tag(response):
    pq_doc = pq(response.body)
    tag_name = response.meta['tag_name']
    for article_div in pq_doc('div#tagged-pages-list div.pages-list-item').items():
        new_article = ScpTagItem(
            title=article_div.text(),
            link=article_div('a').attr('href'),
            tags=tag_name,
        )
        yield new_article


def parse_offset(response):
    if response.status != 404 and len(response.css('#page-content .list-pages-box.list-page-item')) > 0:
        # offset为空不是404，需要判断这个标签内容是不是为空
        detail_dom = response.css('div#main-content')[0]
        offset_index = int(response.url.split('/')[-1])  # .../scp-xxx/offset/x
        link = response.url[30:]
        title = response.css('div#page-title')[0].css('::text').extract()[0].strip() + '-offset-' + str(offset_index)
        offset_item = ScpBaseItem(link=link, title=title, scp_type=DATA_TYPE['offset'],
                                  detail=detail_dom.extract().replace('  ', '').replace('\n', ''), not_found=0)
        yield offset_item
        offset_request = scrapy.Request(response.url[0:-1] + str(offset_index + 1), callback=parse_offset,
                                        headers=HEADERS, dont_filter=True)
        yield offset_request
