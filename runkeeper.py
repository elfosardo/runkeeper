#!/usr/bin/env python

import re
import json
from requests import Session
from bs4 import BeautifulSoup as bfs
from datetime import datetime
from runkeeperExceptions import InvalidAuhentication, \
                                NoActivityInMonth, \
                                EndpointConnectionError, \
                                ProfileNotFound, \
                                InvalidActivityId, \
                                NoActivitiesFound

class Runkeeper(object):

    def __init__(self, email, password):
        self.email = email
        self.password = password
        self.session = Session()
        self.site = 'https://runkeeper.com'
        self.__profile_username = ''
        self.__authenticate()

    def __authenticate(self):
        """
        Send all POST parameters and check for login validation cookie
        :return: bool
        """
        url = "{site}/login".format(site=self.site)
        hidden_elements = self.__get_hidden_elements()
        hidden_elements['email'] = self.email
        hidden_elements['password'] = self.password
        try:
            valid_authentication = self.session.post(url, data=hidden_elements)
        except:
            raise EndpointConnectionError

        if not valid_authentication.cookies.get('checker'):
            raise InvalidAuhentication

        return True

    def __get_hidden_elements(self):
        """
        Retrieve all <hidden> parameters in form
        :return: dict
        """
        url = "{site}/login".format(site=self.site)
        login_form = self.session.get(url)

        soup = bfs(login_form.text, "html.parser")
        form = soup.find_all('input', {'type': 'hidden'})
        hidden_elements = {element.attrs['name']: element.attrs['value'] for element in form}

        return hidden_elements

    @property
    def profile_username(self):
        """
        Get profile username or ID once logged in by using Session object
        :return: str
        """
        if not self.__profile_username:
            url = "{site}/home".format(site=self.site)
            try:
                home = self.session.get(url)
            except:
                raise EndpointConnectionError

            soup = bfs(home.text, "html.parser")
            profile_url = soup.find('a', {'href': re.compile('/user/[a-zA-Z]|[0-9]/profile')})

            try:
                self.__profile_username = profile_url.attrs['href'].split('/')[2]
            except IndexError:
                raise ProfileNotFound

        return self.__profile_username

    def get_activities_month(self, month, year=None):
        """
        Get activities in specified month and year
        :param month: str (month abbreviated)
        :param year: str (YYYY)
        :return: Activity object
        """
        activity_details = []
        year = year or str(datetime.today().year)

        start_date = "{month}-01-{year}".format(month=month, year=year)
        payload = {"userName": self.profile_username, "startDate": start_date}
        url = "{site}/activitiesByDateRange".format(site=self.site)

        try:
            activities_month_request = self.session.get(url, params=payload)
        except:
            raise EndpointConnectionError

        try:
            activities_month = json.loads(activities_month_request.text)['activities']
        except:
            raise NoActivitiesFound

        if not activities_month:
            raise NoActivityInMonth

        for activity in activities_month[year][month]:
            activity_details.append(activity)

        return [Activity(self, activity) for activity in activity_details]


class Activity(object):

    def __init__(self, runkeeper_instance, info):
        self._runkeeper = runkeeper_instance
        self.session = runkeeper_instance.session
        try:
            self.username = info.get('username')
            self.distance = info.get('distance')
            self.activity_id = info.get('activity_id')
            self.distance_units = info.get('distanceUnits')
            self.elapsed_time = info.get('elapsedTime')
            self.live = info.get('live')
            self.caption = info.get('mainText')
            self.activity_type = info.get('type')
            self.__statsCalories = None
            self.__statsElevation = None
            self.__statsPace = None
            self.__statsSpeed = None
            self.__datetime = None
        except KeyError:
            raise InvalidActivityId


    def _populate(self):
        """
        Stores activity value as object from dictionary key in a variable
        """
        activity_details = self.get_activity_details(self.activity_id)
        self.__datetime = self.get_activity_datetime(self.activity_id)
        self.__statsCalories = activity_details.get('statsCalories')
        self.__statsElevation = activity_details.get('statsElevation')
        self.__statsPace = activity_details.get('statsPace')
        self.__statsSpeed = activity_details.get('statsSpeed')

    def get_activity_details(self, activity_id):
        """
        Returns other useful information from a particular activity
        :param activity_id: String
        :return: JSON Object
        """
        url = "{site}/ajax/pointData".format(site=self._runkeeper.site)
        activity_params = {"activityId": activity_id}
        try:
            activity_request = self.session.get(url, params=activity_params)
        except:
            raise EndpointConnectionError

        try:
            activity_details = json.loads(activity_request.text)
        except:
            raise InvalidActivityId

        return activity_details

    @property
    def calories(self):
        if not self.__statsCalories:
            self._populate()
        return self.__statsCalories

    @property
    def elevation(self):
        if not self.__statsElevation:
            self._populate()
        return self.__statsElevation

    @property
    def pace(self):
        if not self.__statsPace:
            self._populate()
        return self.__statsPace

    @property
    def speed(self):
        if not self.__statsSpeed:
            self._populate()
        return self.__statsSpeed

    def get_activity_datetime(self, activity_id):
        """
        :param activity_id: String
        :return: Locale appropriate date and time representation.
        """
        url = "{site}/user/{profile}/activity/{activity_id}".format(site=self._runkeeper.site,
                                                                    profile=self._runkeeper.profile_username,
                                                                    activity_id=activity_id)
        try:
            activity_datetime_session = self.session.get(url)
        except:
            raise EndpointConnectionError

        soup = bfs(activity_datetime_session.text, "html.parser")
        form = soup.find('div', {'class': 'micro-text activitySubTitle'})
        activity_datetime = [date_params.split('-')[0].rstrip() for date_params in form]
        activity_datetime = (''.join(activity_datetime))
        activity_datetime = datetime.strptime(activity_datetime, '%a %b %d %H:%M:%S %Z %Y')

        return activity_datetime

    @property
    def datetime(self):
        if not self.__datetime:
            self._populate()
        return self.__datetime
