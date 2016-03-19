from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import update
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database_setup import Restaurant, Base, MenuItem
from sqlalchemy import cast, DATE, desc, asc, func
from flask import Flask
from flask import render_template, redirect, url_for
from flask import request

app = Flask(__name__)

Base = declarative_base()
engine = create_engine('sqlite:///restaurantmenu.db')
Base.metadata.bind=engine
DBSession = sessionmaker(bind = engine)
session = DBSession()

class RestaurantMenu:

    @app.route('/')
    @app.route('/restaurants', methods=['GET', 'POST'])
    def getRestaurants():
        res = session.query(Restaurant).all()  
        return render_template('home.html', restaurants=res)
         
    @app.route('/restaurants/new', methods=['GET', 'POST'])
    def addRestaurant():
        if (request.method == 'POST'):
            _name = request.form['add']
            addRestaurant = Restaurant(name=_name)
            session.add(addRestaurant)
            session.commit()
            return redirect(url_for('getRestaurants'))
        else:     
            return render_template('addRestaurant.html')

    @app.route('/restaurants/<int:id>/edit', methods=['GET', 'POST'])
    def editRestaurant(id):
        res = session.query(Restaurant).filter(Restaurant.id == id).one()
        if (request.method == 'POST'):
            res.name = request.form['edit']
            session.add(res)
            session.commit()  
            return redirect(url_for('getRestaurants'))
        else:        
            return render_template('editRestaurant.html', id=id, name=res.name)

    @app.route('/restaurants/<int:id>/delete', methods=['GET', 'POST']) 
    def deleteRestaurant(id):
        res = session.query(Restaurant).filter(Restaurant.id == id).one()
        if (request.method == 'POST'):
            session.delete(res)
            session.commit()  
            return redirect(url_for('getRestaurants'))
        else:          
            return render_template('deleteRestaurant.html', id=id, name=res.name)
    
    @app.route('/restaurants/<int:restaurant_id>/restaurantMenuItem', methods=['GET', 'POST'])
    def getRestaurantMenu(restaurant_id):
        restaurant = session.query(Restaurant).filter_by(id = restaurant_id).one()
        items = session.query(MenuItem).filter_by(restaurant_id = restaurant.id)
        print items.count()
        if items.count() > 0:
            return render_template('index.html', restaurant=restaurant, items=items)
        else:
            return redirect(url_for('newMenuItem', restaurant_id = restaurant.id))
          
    @app.route('/restaurants/<int:restaurant_id>/restaurantMenuItem/new', methods=['GET','POST'])
    def newMenuItem(restaurant_id):
        if request.method == 'POST':
            newItem = MenuItem(name = request.form['name'], description = request.form['description'], price = request.form['price'], course = request.form['course'], restaurant_id = restaurant_id)
            session.add(newItem)
            session.commit()
            return redirect(url_for('restaurantMenu', restaurant_id = restaurant_id))
        else:
            return render_template('newmenuitem.html', restaurant_id = restaurant_id)
    
    @app.route('/restaurants/<int:restaurant_id>/restaurantMenuItem/<int:MenuID>/edit', methods = ['GET', 'POST'])
    def editMenuItem(restaurant_id, MenuID):
        editedItem = session.query(MenuItem).filter_by(id = MenuID).one()
        if request.method == 'POST':
            if request.form['name']:
                editedItem.name = request.form['name']
            session.add(editedItem)
            session.commit()
            return redirect(url_for('restaurantMenu', restaurant_id = restaurant_id))
        else:
            return render_template('editmenuitem.html', restaurant_id = restaurant_id, MenuID = MenuID, item = editedItem)
    
    
    @app.route('/restaurants/<int:restaurant_id>/restaurantMenuItem/<int:menu_id>/delete')
    def deleteMenuItem(restaurant_id, menu_id):
        deleteItem = session.query(MenuItem).filter_by(id = menu_id).one()
        if request.method == 'POST':
            session.delete(deleteItem)
            session.commit()
            return redirect(url_for('restaurantMenu', restaurant_id = restaurant_id))
        else:
            return render_template('deletemenuitem.html', restaurant_id = restaurant_id, item = deleteItem)
    
            
                     
if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)
