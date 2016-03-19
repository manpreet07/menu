from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
import database_setup
import cgi
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database_setup import Restaurant, Base, MenuItem
import datetime
from datetime import timedelta
from sqlalchemy import cast, DATE, desc, asc, func
from flask import Flask

app = Flask(__name__)

Base = declarative_base()
engine = create_engine('sqlite:///restaurantmenu.db')
Base.metadata.bind=engine
DBSession = sessionmaker(bind = engine)
session = DBSession()
restaurants = session.query(Restaurant).order_by(Restaurant.name)

class WebServerHandler(BaseHTTPRequestHandler):

    @app.route('/restaurants')
    def do_GET(self):
        try:
            if self.path.endswith("/restaurants"):
                self.send_response(200)
                self.send_header('Content-type','text/html')
                self.end_headers()
                print restaurants
                output = ""
                output += "<html><body>"
                for restaurant in restaurants:
                    output += "<h1>%s</h1>" % restaurant.name
                    output += "<a href=''>Edit</a>&nbsp;&nbsp;<a href=''>Delete</a>"
                output += "</body></html>"
                self.wfile.write(output)
                print output
                return
            if self.path.endswith("/restaurants/new"):
                self.send_response(200)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                output = ""
                output += "<html><body>"
                output += '''<form method='POST' enctype='multipart/form-data' action='http://localhost:8080/restaurants/new'>
                            <h2>Add new Restaurant</h2>
                            <input name="message" type="text" >
                            <input type="submit" value="Submit"> 
                            </form>'''
                output += "</body></html>"
                self.wfile.write(output)
                print output
                return            
        except:
            pass    
        
    def do_POST(self):
        try:
            self.send_response(301)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            ctype, pdict = cgi.parse_header(
                self.headers.getheader('content-type'))
            if ctype == 'multipart/form-data':
                fields = cgi.parse_multipart(self.rfile, pdict)
                messagecontent = fields.get('message')
            output = ""
            output += "<html><body>"
            output += "<h1> %s restaurant added</h1>" % messagecontent[0]
            output += '''<form method='POST' enctype='multipart/form-data' action='http://localhost:8080/restaurants/new'>
                        <h2>Add new Restaurant</h2>
                        <input name="message" type="text" >
                        <input type="submit" value="Submit"> 
                        </form>'''
            output += "</body></html>"
            self.wfile.write(output)
            restaurant = Restaurant(name=messagecontent[0])
            session.add(restaurant)
            session.commit()            
            print output
        except:
            pass
                    
    @app.route('/')
    def hello_world():
        return 'Hello World!'
    
if __name__ == '__main__':
#     app.run(host='0.0.0.0', debug=True)
    main()