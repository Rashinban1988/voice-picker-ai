from django.shortcuts import render

from .models import User, Organization

def create_organization(name, phone_number):
    return Organization(name, phone_number)

def create_user(sei, mei, email, password, phone_number):
    return User(sei, mei, email, phone_number)
