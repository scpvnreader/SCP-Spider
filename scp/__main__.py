# -*- coding: utf-8 -*-

from .core import ScpSpider
import sys
#
options = sys.argv[1:]
c = ScpSpider()
if not {'main', 'single', 'offset', 'collection', 'test'} & set(options):
    print('Please provide a notification option: "news" or "follow"')
    sys.exit(0)
else:
    c.crawl_this_spider(options[0])
#
# if __name__ == '__main__':
# c = ScpSpider()
# c.crawl_main_list()
# c.crawl_single_pages()
# c.crawl_collection_pages()
# c.crawl_offset_pages()
# c.crawl_main_detail()
# c.split_csv()
