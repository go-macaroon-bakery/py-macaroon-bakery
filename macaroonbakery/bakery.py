# Copyright 2016 Canonical Ltd.
# Licensed under the AGPLv3, see LICENCE file for details.

import base64
import json
import requests
import webbrowser

import macaroons


def deserialize(json_macaroon):
    '''Deserialize a JSON macaroon into a macaroon object.

    @param the JSON macaroon to deserialize.
    @return the deserialized macaroon.
    '''
    return macaroons.deserialize(to_base64(json_macaroon))


def to_base64(json_macaroon):
    '''Base 64 encode a json macaroon

    @param the JSON macaroon to encode.
    @return the encoded macaroon.
    '''
    return base64.urlsafe_b64encode(json.dumps(json_macaroon))


def add_padding(s):
    '''Add padding to base64 encoded string
    libmacaroon does not give padded base64 string from serialization

    @param string s to be padded
    @return a padded string
    '''
    return s + '=' * ((4 - (len(s) % 4)) % 4)


def serialize_macaroon_string(macaroon):
    '''Serialize macaroon to string

    @param macaroon to be serialized
    @return a string serialization form of the macaroon
    '''
    return base64.urlsafe_b64decode(
        add_padding(macaroon.serialize_json()))


class DischargeError(Exception):
    pass


class Bakery(object):
    ''' Bakery is a wrapper around requests that ensures
    that macaroons headers are sent to the server if present or gather the
    discharged macaroons automatically before sending the request.
    '''
    def __init__(self, initial_macaroons=None, discharge_token=None,
                 timeout=30):
        '''
        @param initial_macaroons initial macaroon to be used in headers.
        @param discharge_token initial discharge token.
        @param timeout timeout for wait url.
        '''
        self.macaroons = initial_macaroons
        self.discharge_token = discharge_token
        self.timeout = timeout

    def get(self, url, **kwargs):
        '''Act as the same than requests.get, same arguments,
        same returned value, same exception raised except DischargeError
        when something wrong happened when discharging.
        If macaroons are present, the headers will be augmented with it.
        '''
        if self.macaroons is not None:
            if 'headers' not in kwargs:
                kwargs['headers'] = {}
            kwargs['headers']['Bakery-Protocol-Version'] = 1
            kwargs['headers']['Macaroons'] = self.macaroons

        response = requests.get(url, **kwargs)
        if (response.status_code == 401 and
                response.headers['Www-Authenticate'] == 'Macaroon') \
                or response.status_code == 407:
            try:
                response_json = response.json()
            except ValueError:
                raise DischargeError(
                    'Unable to get data from unauthorized response')
            if 'Code' not in response_json:
                raise DischargeError(
                    'Unable to access code from unauthorized response')

            if response_json['Code'] == 'macaroon discharge required':
                if 'Info' not in response_json \
                        or 'Macaroon' not in response_json['Info']:
                    raise DischargeError(
                        'Unable to access info from unauthorized response')
                macaroon = deserialize(response_json['Info']['Macaroon'])
                discharges = self._discharge(macaroon)
                encoded_discharges = map(serialize_macaroon_string, discharges)
                self.macaroons = base64.urlsafe_b64encode(
                    '[' + ','.join(encoded_discharges) + ']')
                return self.get(url, **kwargs)

        return response

    def _discharge(self, macaroon):
        '''Discharge a macaroon.

        @param the macaroon to discharge.
        @returns the discharged macaroons.
        @raise DischargeError when an error occurs during the discharge
        process.
        '''
        discharges = [macaroon]
        first_party_location = macaroon.location
        self._discharge_caveats(macaroon, discharges, first_party_location,
                                macaroon)
        return discharges

    def _discharge_caveats(self, macaroon, discharges, first_party_location,
                           primary_macaroon):
        '''Gathers discharge macaroons for all the third party caveats
        for the macaroon passed in.

        @param macaroon the macaroon to discharge.
        @param discharges the list of discharged macaroons.
        @param first_party_location the location of the first party.
        @param primary_macaroon used for signature of the discharge macaroon.
        @raise DischargeError when an error occurs during the discharge
        process.
        '''
        caveats = macaroon.third_party_caveats()
        for caveat in caveats:
            dm = self._get_discharge(first_party_location,
                                     caveat[0],
                                     caveat[1])
            dm = primary_macaroon.prepare_for_request(dm)
            discharges.append(dm)
            self._discharge_caveats(dm, discharges, first_party_location,
                                    primary_macaroon)

    def _get_discharge(self, location, third_party_location, condition):
        ''' Get the discharge macaroon from the third party location.

        @param location the origin.
        @param third_party_location where to get a discharge from.
        @param condition associated  to the discharged macaroon.
        @return a discharged macaroon.
        @raise DischargeError when an error occurs during the discharge
        process.
        '''
        headers = {'Bakery-Protocol-Version': 1}
        if self.discharge_token is not None:
            headers['Macaroons'] = self.discharge_token
        payload = {'id': condition, 'location': location}

        try:
            response = requests.post(third_party_location + '/discharge',
                                     headers=headers,
                                     data=payload,
                                     timeout=self.timeout)
        except requests.RequestException as exc:
            raise DischargeError(
                'Unable to access discharge endpoint: {}'.format(exc.message))
        if response.status_code == 200:
            try:
                response_json = response.json()
            except ValueError:
                raise DischargeError(
                    'Unable to access data from discharge endpoint on 200')

            if 'Macaroon' not in response_json:
                raise DischargeError(
                    'Unable to access macaroon from discharge endpoint on 200')
            return deserialize(response_json['Macaroon'])

        if response.status_code == 401:
            try:
                response_json = response.json()
            except ValueError:
                raise DischargeError(
                    'Unable to access json from discharge endpoint on 401')

            if 'Code' not in response_json:
                raise DischargeError(
                    'Unable to access code from discharge endpoint on 401')

            if response_json['Code'] == 'interaction required':
                if 'Info' not in response_json:
                    raise DischargeError(
                        'Unable to access info from discharge endpoint on 401')
                if 'VisitURL' not in response_json['Info'] \
                        or 'WaitURL' not in response_json['Info']:
                    raise DischargeError(
                        'Unable to access wait or visit url from discharge '
                        'endpoint on 401')
                webbrowser.open(response_json['Info']['VisitURL'], new=1)
                try:
                    resp = requests.get(response_json['Info']['WaitURL'],
                                        timeout=self.timeout)
                except requests.RequestException as exc:
                    raise DischargeError(
                        'Unable to access wait url: {}'.format(exc.message))
                if resp.status_code == 200:
                    try:
                        response_json = resp.json()
                    except ValueError:
                        raise DischargeError(
                            'Unable to access json macaroon from wait url'
                        )
                    if 'DischargeToken' not in response_json \
                            or 'Macaroon' not in response_json:
                        raise DischargeError(
                            'Unable to access macaroon or discharge token from'
                            ' discharge endpoint'
                        )
                    if self.discharge_token is None:
                        self.discharge_token = to_base64(
                            response_json['DischargeToken'])
                    return deserialize(response_json['Macaroon'])
                else:
                    raise DischargeError(
                        'Unexpected status code from wait url: {}'.format(
                            resp.status_code
                        ))
            else:
                raise DischargeError(
                    'Ununexpected Code on discharge endpoint: {}'.format(
                        response_json['Code']))
        raise DischargeError(
            'Unexpected status code from discharge endpoint: {}'.format(
                response.status_code))
