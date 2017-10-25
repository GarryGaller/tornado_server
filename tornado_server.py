#!/usr/bin/env python3

#--------------------------------------
"""
Script      : tornado_server.py
Desсription : Cервер на основе фреймворка Tornado для листинга директорий
Author      : Gary Galler
Copyright(C): Gary Galler, 2017.  All rights reserved
Version     : 1.0.0.0
Date        : 24.10.2017
"""
#--------------------------------------
__version__ = '1.0.0.0'
__date__    = '24.10.2017'


import os,sys
import tornado.ioloop
from tornado.web import HTTPError,Application,URLSpec as url
from tornado.escape import xhtml_unescape
import tornado
import mimetypes
from urllib.parse import quote,unquote
import http
import re
#для автоопределения кодировки файлов
from chardet.universaldetector import UniversalDetector

if os.name == "nt" and sys.version_info[:2] < (3,6):
    import win_unicode_console
    win_unicode_console.enable()

#arguments - все аргументы GET и POST запроса
#files - все загруженные файлы (через запросы multipart/form-data POST)
#path - путь запроса (все, что находится в строке запроса перед ?)
#headers - заголовки запроса


#---------------------------------
# дебаговый вывод информации
#---------------------------------
def debug_response_headers(self):
    print("-"*10)
    print("RESPONSE:")
    print(self.request.version,self.get_status())
    print(self._headers)

def debug_request_headers(self):
    print("-"*10)
    path = unquote(self.request.path)
    print("CONNECTED:",self.request.host)
    print(
        self.request.method, 
        path,
        self.request.version
    )
 
    print(self.request.headers)

#---------------------------------
# чтение файла
#---------------------------------
async def read_file(filepath):
    data = open(filepath,"rb").read()
    return data,int(len(data))

#---------------------------------
# определение кодировки файла
#---------------------------------
async def detect_encoding(filepath):
    default_encoding = sys.getfilesystemencoding()
    #default_enc = locale.getpreferredencoding()
    result = None
    detector = UniversalDetector()
    detector.reset()
    
    for line in open(filepath, 'rb'):
        detector.feed(line)
        if detector.done: break
    detector.close()
    encoding = detector.result.get('encoding') or default_encoding
    
    return encoding

#---------------------------------
# листинг каталогов
#---------------------------------
async def list_directory(root):
    
    cache_dirs = CASCHE_DIRS.get(root)
    if cache_dirs:
        return cache_dirs
    dirs  = []
    files = []
    
    for name in os.listdir(root):
        if os.path.isdir(os.path.join(root,name)):
            dirs.append(name.upper() + "/")
        else:
            files.append(name)
    
    dirs.sort()
    files.sort()
    dirs.extend(files)
    CASCHE_DIRS[root] = dirs
    return dirs

#---------------------------------
# базовый обработчик маршрутов
#---------------------------------
class BaseHandler(tornado.web.RequestHandler):
    
    # переопределенный метод для выдачи страницы ошибки
    def write_error(self, status_code, **kwargs):
        #print(httputil.responses[status_code])
        http_status = STATUS_CODES[status_code]
        
        self.set_status(404)
        self.write(
            self.render_string(
                "static/error.html",
                title="Ой! Ошибочка вышла...", 
                status_code="{0} {1}".format(status_code,http_status.phrase),
                message=http_status.description,
                traceback=unquote(self.request.path))
                )
        self.finish()
        debug_response_headers(self)
        return


#---------------------------------
# обработчик корневого маршрутов
#---------------------------------
class RootHandler(BaseHandler):
    
    async def get(self,*args,**kwargs):
        # дебаговый вывод в консоль
        debug_request_headers(self)
        
        items = await list_directory(ROOT)
        self.render("static/listing.html",
                    title="/", 
                    items=items)
        # дебаговый вывод в консоль
        debug_response_headers(self)
        return

#---------------------------------
# обработчик остальных маршрутов
#---------------------------------        
class OtherHandler(BaseHandler):
    
    async def get(self,*args,**kwargs):
        
        filename = unquote(self.request.path)
        filepath = os.path.normpath(os.path.join(
                    ROOT,filename.strip('/'))
                    )
        
        typ,enc = mimetypes.guess_type(filename)
        # файлам без типа приписываем тип двоичного файла без указания формата 
        if typ is None:
            typ = 'application/octet-stream'
    
        #filepath = unquote(filepath)
        # дебаговый вывод в консоль
        debug_request_headers(self)
        print('-'* 10)
        print(filepath,typ)
        
        if os.path.exists(filepath):
            # если запрашиваемый ресурс - директория, выводим листинг
            if os.path.isdir(filepath):
                items = await list_directory(filepath)
                self.render("listing.html",
                            title=unquote(self.request.path),
                            items=items)
                # дебаговый вывод в консоль
                debug_response_headers(self)
                return           
            else:
                if text_types.match(typ):
                    # если файл текстовый - определяем кодировку для того, 
                    # чтобы браузер мог его правильно отобразить
                    encoding = await detect_encoding(filepath)
                    content_type = "{}; charset={}".format(typ,encoding)  
                else:
                    # на все прочие бинарники будем заставлять браузер открывать диалог сохранения файла
                    # кроме тех типов файлов, которые мы исключили (картинки, видео, pdf), 
                    # так как их браузер умеет открывать сам 
                    if not browser_types.match(typ):
                        self.set_header('Content-Description', 'File Transfer')
                        self.set_header('Content-Transfer-Encoding','binary')
                        # этот заголовок заставляет браузер показать диалог сохранения файла
                        self.set_header('Content-Disposition',
                            'attachment;filename=%s' % quote(os.path.basename(filepath)))  
                            # если использовать urlencoded квотирование добавлять * не нужно 
                            # если здесь убрать * - имя не будет декодировано
                            #"attachment;filename*=UTF-8''%s" % os.path.basename(filepath).encode('utf-8')) 
                    content_type = typ
                
                data,size = await read_file(filepath)
                self.set_status(200)    
                self.set_header("Content-Type", content_type)
                self.set_header('Content-Length', size)
                self.write(data)
                self.flush()
                # дебаговый вывод в консоль
                debug_response_headers(self)
                return
        # если файл не найден        
        else:
             # используем свой шаблон для генерации страницы ошибки
             # переопределяя write_error
             return self.send_error(404)
             
# можно  просто вызвать ошибку и получить дефолтную страницу
#             raise HTTPError(
#                status_code=404,
#                reason="File Not Found: %s" % filepath
#             )

        
#---------------------------------
# создание обработчиков маршрутов
#---------------------------------             
def make_app():
    return Application([
        url(r"/",     RootHandler, name='root'),    # обработчик корневого пути
        url(r"/(.+)", OtherHandler, name="ohter"),  # обработчик всех прочих путей
    ])


#==============================================
if __name__ == "__main__":
    CASCHE_DIRS = {}
    ROOT = os.path.dirname(__file__)
    DEFAULT_CHARSET = "utf-8"
    #STATUS_CODES = {status.value:status for status in http.HTTPStatus}
    STATUS_CODES = {status.value:status for status in tornado.httputil.responses}
    # получаем словарь вида
#    {428: <HTTPStatus.PRECONDITION_REQUIRED: 428>, 
#    429: <HTTPStatus.TOO_MANY_REQUESTS: 429>, 
#    400: <HTTPStatus.BAD_REQUEST: 400>, 
#    401: <HTTPStatus.UNAUTHORIZED: 401>, 
#    402: <HTTPStatus.PAYMENT_REQUIRED: 402>, 
#    403: <HTTPStatus.FORBIDDEN: 403>, 
#    404: <HTTPStatus.NOT_FOUND: 404>,
#    ...} ; объект status[code] имеет свойства name и phrase
    
    if not mimetypes.inited:
        mimetypes.init() 
    
    # добавляем и переопределяем некоторые mime типы
    mimetypes.types_map.update(
        {
        ""     :'application/octet-stream', # файлам без расширения дадим дефолтный тип неизвестного двичного содержимого 
        ".json":"application/json", # отсутствует
        ".vbs" :"text/plain",       # отсутствует
        ".csv" :"text/plain",       # переопределяем для открытия в браузере
        ".djvu":"application/djvu", # отсутствует
        ".js"  :"text/plain",       # переопределяем
        }
        )
    
    # типы, которые нужно открывать текстовом режиме и декодировать
    text_types = re.compile("|".join(
        ["text/.*","application/json"]
        ))
    
    # типы, которые мы хотим, чтобы браузер открывал сам
    browser_types = re.compile("|".join(
        [
        "application/json",
        "application/pdf",
        "image/.*",
        "video/.*"
        ]
        ))
    
    PORT,HOST =  8888,'localhost'
    app = make_app()
    app.listen(PORT,HOST)
    print('START LISTEN SERVER:{}:{}'.format(PORT,HOST))
    tornado.ioloop.IOLoop.current().start()
      
    
    
