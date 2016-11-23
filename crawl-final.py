# -*- coding: utf-8 -*-

import requests
import pickle
import random
import os
import string
#import pymysql
import time
import json
import re
from html.parser import HTMLParser

#如果一直使用一个spm会出现404，这里读取预先存好的spmlist，用random选择来避免
with open("spm.pkl", "rb") as spmfile:
	spmlist = pickle.load(spmfile)

class rating:#好中差评的数量
	def __init__(self):
		self.good = 0
		self.neutral = 0
		self.bad = 0
		

class iconinfo:
	def __init__(self):
		self.vip = "" 				#vip等级，none代表不是
		self.sina = 0 				#1代表是新浪大V，0不是
		self.yellow = 0				#1代表是黄钻，0不是
		self.taonvlang = 0			#1代表是淘女郎，0不是
		self.good = []				#好评列表
		self.neutral = []			#中评
		self.bad = []				#差评
		self.seasonsale = 0			#最近三个月销量
		self.sellercredit = 0		#卖家信用
		self.buyercredit = 0		#买家信用
		self.weekly = rating()		#最近一周的评价数
		self.monthly = rating()		#最近一月的评价数
		self.halfyr = rating()		#最近半年的评价数
		self.before = rating()		#半年前的评价数


class maijia:
	def __init__(self):
		self.addrs = ""				#卖家的网址，用来扒vip，新浪大V等信息
		self.name = ""				#卖家昵称
		self.info = iconinfo()		#卖家信息
		self.exist = False			#卖家是否在数据库中存在

		
class tag:
	def __init__(self):
		self.old = 0.00				#商品原价，-1代表没有原价
		self.new = 0.00				#二手价格
		self.descaddrs = ""			#商品描述的地址
		self.idcode = ""			#卖家的idcode（唯一）
		
		
class goods:
	def __init__(self):
		self.addrs = ""				#商品地址
		self.name = ""				#商品名称
		self.id = ""				#商品id
		self.price = tag()			#进入商品页面后能扒到的信息
		self.dscrpt = ""			#商品描述
		self.seller = maijia()		#商品卖家
		self.comm = 0				#商品留言数量
		self.mark = 0				#商品收藏数量
		self.commlist = ""			#商品留言


#打开网页
def url_open(url):
	temptation = 0
	success = False
	html = ""
	while temptation < 3 and not success:
		try:
			headers = {"User-Agent": "Mozilla/5.0 (Windows NT 6.3; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0"}
			r = requests.get(url, headers = headers)
			html = r.text
			success = True
		except Exception as reason:
			temptation += 1
			print("tried %d times, error" % temptation)
		finally:
			if not success:
				print("visit fail")
	return html


#打开需要登陆的网页
def url_login(url):
	temptation = 0
	success = False
	html = ""
	while temptation < 3 and not success: #给三次机会，都不成功就输出visit fail
		try:
			headers = {
				"User-Agent": "Mozilla/5.0 (Windows NT 6.3; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0",
				"Cookie": ""#COOKIE
			}
			r = requests.get(url, headers = headers)
			html = r.text
			success = True
		except Exception as reason:
			temptation += 1
			print("tried %d times, error" % temptation)
		finally:
			if not success:
				print("visit fail")
	return html


#获取留言
def get_comm(url, id, page):
	params = {"itemId": id, "pageNumber": str(page), "rowsPerPage": '10', "t": '1448200802718', "_tb_token_": 'e5b933313393e'}#参数t和_tb_token_在网页上爬不到，但是一段时间后会失效，故要过一段时间手动抓取
	referer = "https://2.taobao.com/item.htm?spm=2007.1000337.16.4.ZG6V3V&id=" + id
	headers = {
		"Accept":"application/json, text/javascript, */*; q=0.01",
		"Accept-Encoding":"gzip, deflate",
		"Accept-Language":"zh-CN,zh;q=0.8,en-US;q=0.5,en;q=0.3",
		"Connection":"keep-alive",
		"Content-Type":"application/x-www-form-urlencoded; charset=UTF-8",
		"Cookie": "",#COOKIE
		"Host":"2.taobao.com",
		"Referer":referer,
		"User-Agent":"Mozilla/5.0 (Windows NT 6.3; WOW64; rv:41.0, Gecko/20100101 Firefox/41.0",
		"X-Requested-With":"XMLHttpRequest",
	}
	r = requests.get(url, params=params, headers=headers)
	return r.json()


#获取进入商品页面后的信息：价格、描述地址、卖家的idcode（为了减少登陆浏览的次数，只能整合在一起）
def get_price(url):
	html = url_login(url)
	price = tag()
	newp = re.search(r"<em>\d+\.\d*", html)
	oldp = re.search(r"<span>\d+\.\d*", html)
	newp = float(newp.group(0).split(">")[-1])
	if oldp:
		oldp = float(oldp.group(0).split(">")[-1])
	else:
		oldp = -1
	price.new = newp
	price.old = oldp
	a = re.search(r'userIdCode=.*?"', html)
	price.idcode = a.group(0)[11 : -1]
	
	i = html.find('id="desc-intro"')
	j = html.find('data-url', i)
	k = html.find('" class', j)
	tmp = 'http:' + html[j + 10 : k]
	price.descaddrs = tmp
	return price
	

#获取商品描述
def get_dscrpt(url):
	ctx = url_open(url)
	d = ctx.find("='")
	e = ctx.find("';", d)
	s = ctx[d + 2 : e]
	t = re.findall(r">.*?<", s)
	tmp = []
	for each in t:
		tmp.append(each[1:-1])
	if len(tmp) != 0:
		dscrpt = "".join(tmp)
	else:
		dscrpt = s
	return dscrpt
	

#测试卖家是否已经在数据库中
def seller_exist(idcode):
	conn = pymysql.connect(host = 'localhost', port = 3306, user = 'root', passwd = '0', db = 'xianyu', charset = 'utf8')
	cur = conn.cursor()
	sta = cur.execute("select * from sellerinfo where idcode = " + idcode + " limit 1") #找到第一个为止
	if sta == 0: #找到了0个
		return False
	else:		 #不然存在
		return True


#获取商家信息
def get_seller_info(url, idcode):
	
	#以下第一部分是获取vip、黄钻、新浪、淘女郎等信息
	html = url_open(url)
	info = iconinfo()
	a = html.find('seller-icon')
	b = html.find('>vip', a)
	if b != -1:
		info.vip = html[b + 1 : b + 5]
	else:
		info.vip = "none"
	c = html.find('sinav', a)
	if c != -1:		
		info.sina = 1
	else:
		info.sina = 0
	d = html.find('yellow', a)
	if d != -1:
		info.yellow = 1
	else:
		info.yellow = 0
	e = html.find('taonvlang', a)
	if e != -1:
		info.taonvlang = 1
	else:
		info.taonvlang = 0
	
	#以下第二部分是获取卖家最近三个月的销量	和这个页面上的最近评价
	rateurl = "https://2.taobao.com/credit/credit.htm?spm=" + random.choice(spmlist) + "&userIdCode=" + idcode
	data = url_login(rateurl)
	a = data.find("J_ItemCount")
	b = data.find("<", a)
	info.seasonsale = int(data[a + 13 : b])
	s = re.search(r'userNumId" value="\d+', data)
	numid = s.group(0).split('"')[-1]
	url = "https://rate.taobao.com/used_idle_rate_list.htm?currentPageNum=1&userNumId=" + numid + "&auctionNumId&showContent=1&_ksTS=1448191033876_33&callback=jsonp34"
	referer = 'https://2.taobao.com/credit/credit.htm?spm=' + random.choice(spmlist) + '&userIdCode=UvG8SvmcLvCIY'
	headers = {
		'Host': 'rate.taobao.com',
		'User-Agent': 'Mozilla/5.0 (Windows NT 6.3; WOW64; rv:42.0) Gecko/20100101 Firefox/42.0',
		'Accept': '*/*',
		'Accept-Language': 'zh-CN,zh;q=0.8,en-US;q=0.5,en;q=0.3',
		'Accept-Encoding': 'gzip, deflate',
		'Referer': referer,
		'Cookie': 'thw=cn; cna=5+UxEKx46zkCAdprhJbs6Nh+; v=0; cookie2=1c225e553e62af044167283e3886ed11; t=dfef82c06f083df1fde96fce6f60a08f; l=AmBg27vbSX1SzgxrqsILQUfCMGUyxEQz; isg=AszMm0PE97XbnuNJIZb-kgQWnCoYaHCvtmWk0CaNdXcasW67ThfbPjZJJwdv; _tb_token_=e3b363e733495; uc1=cookie14=UoWwJMH%2FCjBxPw%3D%3D&lng=zh_CN&cookie16=V32FPkk%2FxXMk5UvIbNtImtMfJQ%3D%3D&existShop=false&cookie21=Vq8l%2BKCLjhS4UhJVbhgU&tag=2&cookie15=V32FPkk%2Fw0dUvg%3D%3D&pas=0; uc3=sg2=AH4M0CY6WC0XrBCJ6MhvOGO5glAn3W7oAnomTlPeWqg%3D&nk2=CdzvE23KCwIK&id2=UonTHiMKbE3u4A%3D%3D&vt3=F8dAS1UBtoDWAAHIOcU%3D&lg2=W5iHLLyFOGW7aA%3D%3D; existShop=MTQ3MDgyMjQ4NA%3D%3D; uss=URtAtt%2FZNM8mFrmFuR7cCSA0t77ghv8uxqW6Gy3QuC%2B3VJ18BTj3hMeFBs4%3D; lgc=joss_wang; tracknick=joss_wang; sg=g8f; mt=ci=1_1; cookie1=VFCuIXsgwDIBqMlTC9naQzYY241rd7JhW5O77GkvciY%3D; unb=1883666168; skt=3464913508d91bdc; _cc_=U%2BGCWk%2F7og%3D%3D; tg=0; _l_g_=Ug%3D%3D; _nk_=joss_wang; cookie17=UonTHiMKbE3u4A%3D%3D; x=e%3D1%26p%3D*%26s%3D0%26c%3D0%26f%3D0%26g%3D0%26t%3D0%26__ll%3D-1%26_ato%3D0; whl=-1%260%260%261470822651147',#COOKIE
		'Connection': 'keep-alive'
	}
	data = requests.get(url, headers = headers)
	ctx = data.text.split("(")[-1].split(")")[0]
	s = json.loads(ctx)
	if s["comments"] != None:
		info.good.append("；".join([ x["content"] for x in s["comments"] ]))
		
	
	
	#以下第三部分：部分卖家是在淘宝上有自己的店铺的，只有有店铺的人才能进入到那个页面扒以前的评价、买卖的信用，没有店铺的人会被跳转到个人主页，没有有价值的信息
	sellerurl = "https://rate.taobao.com/user-rate-" + idcode + ".htm?spm=" + random.choice(spmlist)
	html = url_open(sellerurl)
	title = re.search(r"<title>.*?<", html)
	judge = title.group(0)[7 : -1]
	
	if judge != '个人主页': #判断是否开了店铺，开店的执行以下
		#获得买卖家信用
		s = re.search(r"卖家信用：\d+", html)
		info.sellercredit = int(s.group(0).split("：")[-1])
		r = re.compile(r"买家信用：.*?<a href", re.DOTALL)
		s = re.search(r, html).group(0)
		info.buyercredit = int(re.search(r"\d+", s).group(0))
		
		#获得最近一周、一月、半年、半年前的好中差评数量
		r = re.compile(r'rateok">.*?</td>', re.DOTALL)
		s = re.findall(r, html)
		info.weekly.good = int(re.search(r'\d+', s[0]).group(0))
		info.monthly.good = int(re.search(r'\d+', s[1]).group(0))
		info.halfyr.good = int(re.search(r'\d+', s[2]).group(0))
		info.before.good = int(re.search(r'\d+', s[3]).group(0))
		
		r = re.compile(r'ratenormal">.*?</td>', re.DOTALL)
		s = re.findall(r, html)
		info.weekly.neutral = int(re.search(r'\d+', s[0]).group(0))
		info.monthly.neutral = int(re.search(r'\d+', s[1]).group(0))
		info.halfyr.neutral = int(re.search(r'\d+', s[2]).group(0))
		info.before.neutral = int(re.search(r'\d+', s[3]).group(0))
	
		r = re.compile(r'ratebad">.*?</td>', re.DOTALL)
		s = re.findall(r, html)
		info.weekly.bad = int(re.search(r'\d+', s[0]).group(0))
		info.monthly.bad = int(re.search(r'\d+', s[1]).group(0))
		info.halfyr.bad = int(re.search(r'\d+', s[2]).group(0))
		info.before.bad = int(re.search(r'\d+', s[3]).group(0))
		
		#爬取好中差评的内容
		for num in [1, 0, -1]:
			page = 1
			end = False
			while not end:
				rateurl = "https://ratehis.taobao.com/user-rate-" + idcode + "--isarchive|true--buyerOrSeller|0--receivedOrPosted|0--goodNeutralOrBad|" + str(num) + "--timeLine|--detailed|--ismore|0--showContent|--timeLine|--buyerOrSeller|0--goodNeutralOrBad|--detailed|--receivedOrPosted|0--showContent|--currentPage|" + str(page) + "--ismore|0--maxPage|" + str(page) + ".htm#RateType"
				data = url_login(rateurl)
				s = re.findall(r"&#[\d&#;]+;", data)			#这里找到的评价都是类似'&#12345;'这样的unicode码
				if len(s) == 0:
					end = True
				else:
					for each in s:
						h = HTMLParser()						#用HTMLParser可以解码这些中文
						if num == 1:
							info.good.append(h.unescape(each))
						elif num == 0:
							info.neutral.append(h.unescape(each))
						else:
							info.bad.append(h.unescape(each))
					page += 1
	'''	
	else: #没有店铺的人
		print("i don't know what to do")
	'''	
	return info
	

#获取商品	
def find_items(url):
	html = url_open(url)
	items = []	#用这个列表存储每个商品
	a = html.find('h4 class')
	
	while a != -1: 		#建立循环 寻找页面上的所有商品
		item = goods()	#每个商品都是goods类
		b = html.find('href="', a)
		c = html.find('">', b)
		raw = "https:" + html[b + 6 : c]
		raw = raw.split('?')
		
		item.id = raw[1][3:-1] + raw[1][-1]				#获取商品id
		url = "https://2.taobao.com/comment/queryCommentList.do"
		page = 1
		end = False
		templist = []
		while not end:
			s = get_comm(url, item.id, page)
			templist.append("；".join([ x["content"] for x in s["result"]["commentList"] ]))
			if s['result']['nextPage'] != False:
				page += 1
			else:
				end = True
		item.commlist = "；".join(templist)			#获取商品留言
				
		tmp = raw[0] + "?spm=" + random.choice(spmlist) + "&" + raw[1]
		item.addrs = tmp
		item.price = get_price(tmp)						#获取商品价格等信息
		item.dscrpt = get_dscrpt(item.price.descaddrs)	#获取商品描述
		
		d = html.find('</a>', c)
		tmp = html[c + 2 : d]
		item.name = tmp									#获取商品名称
		
		if not seller_exist(item.price.idcode):			#如果数据库中没有这个卖家的话再执行下面的内容
			e = html.find('seller-nick">',d)
			f = html.find('href="', e)
			g = html.find('" class', f)
			tmp = "https:" + html[f + 6 : g] + '&ist=1'
			item.seller.addrs = tmp
			item.seller.info = get_seller_info(tmp, item.price.idcode)
			
			h = html.find('data-nick', g)
			i = html.find('" data-icon', h)
			tmp = html[h + 11 : i]
			item.seller.name = tmp
		else:											#如果已存在则把exist置为True
			item.seller.exist = True
		
		j = html.find('留言<em', d)
		k = html.find('</em>', j)
		l = html.find('收藏<em', k)
		m = html.find('</em>', l)
		item.comm = int(html[j + 21 : k])				#获取留言、收藏数
		item.mark = int(html[l + 21 : m])
		
		items.append(item)
		
		a = html.find('h4 class', i)
	
	return items


#用pickle模块存储最后获取的items列表作为备份
def save_items(filename, items):
	with open(filename, "wb") as file:
		pickle.dump(items, file)

'''
#转移入数据库
#数据库里的表已经建好了，数据库名xianyu，表名nvzhuang和sellerinfo
#nvzhuang的列有：id(char), name(char), pricenew(float), priceold(float), comm(int), mark(int), seller(char), dscrpt(char), commlist(char)
#其中商品id是唯一的
#sellerinfo的列有：idcode(char), name(char), vip(char), sina(int), yellow(int), taonvlang(int), seasonsale(int), sellercredit(int), buyercredit(int), weeklygood(int), weeklyneutral(int), weeklybad(int), monthlygood(int), monthlyneutral(int), monthlybad(int), halfyrgood(int), halfyrneutral(int), halfyrbad(int), beforegood(int), beforeneutral(int), beforebad(int), goodrate(char), neutralrate(char), badrate(char)
#其中idcode和seller的name都是唯一的
#以及dscrpt, commlist, good\neutral\badrate 这些列需要很长的char长度
def trans_sql(items):
	conn = pymysql.connect(host = 'localhost', port = 3306, user = 'root', passwd = '20131427', db = 'xianyu', charset = 'utf8')
	cur = conn.cursor()
	for item in items:
		sta1 = cur.execute("insert into nvzhuang values ('" item.id + "', '" + item.name + "', " + str(item.price.new) + ", " + str(item.price.old) + ", " + str(item.comm) + ", " + str(item.mark) + ", '" + item.seller.name + "', '" + item.dscrpt + "', '" + item.commlist + "');")
		if not item.seller.exist: #如果卖家不存在再传入数据库
			sta2 = cur.execute("insert into sellerinfo values ('" item.price.idcode + "', '" + item.seller.name + "', '" + item.seller.info.vip + "', " + str(item.seller.info.sina) + ", " + str(item.seller.info.yellow) + ", " + str(item.seller.info.taonvlang) + ", " + str(item.seller.info.seasonsale) + ", " + str(item.seller.info.sellercredit) + ", " + str(item.seller.info.buyercredit) + ", " + str(item.seller.info.weekly.good) + ", " + str(item.seller.info.weekly.neutral) + ", " + str(item.seller.info.weekly.bad) + ", " + str(item.seller.info.monthly.good) + ", " + str(item.seller.info.monthly.neutral) + ", " + str(item.seller.info.monthly.bad) + ", " + str(item.seller.info.halfyr.good) + ", " + str(item.seller.info.halfyr.neutral) + ", " + str(item.seller.info.halfyr.bad) + ", " + str(item.seller.info.before.good) + ", " + str(item.seller.info.before.neutral) + ", " + str(item.seller.info.before.bad) + ", '" + "；".join(item.seller.info.good) + "', '" + "；".join(item.seller.info.neutral) + "', '" + "；".join(item.seller.info.bad) + "';")
		conn.commit()	#确认上述执行，不然数据会丢失
	cur.close()
	conn.close()
'''

#下载数据
def download(spm, page_num):
	url = "https://s.2.taobao.com/list/list.htm?spm=" + spm + "&catid=50446013&st_trust=1&page=" + str(page_num) + "&ist=0"
	items = find_items(url)		#开始获取数据
	
	now = time.localtime()		#获取当前时间，生成备份文件名
	filename = "items" + str(now.tm_year) + str(now.tm_mon) + str(now.tm_mday) + "-" + str(now.tm_hour) + "." + str(now.tm_min) + "." + str(now.tm_sec) + ".pkl"
	save_items(filename, items) #先在本地备份
	#trans_sql(items)			#再传入数据库
	
#main
if __name__ == "__main__":
	download(random.choice(spmlist), 1) #只爬第一页的，可以做循环爬所有页的