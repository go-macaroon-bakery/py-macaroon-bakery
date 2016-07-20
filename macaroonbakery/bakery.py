# Copyright 2016 Canonical Ltd.
# Licensed under the LGPLv3, see LICENCE file for details.

import base64
import json
import webbrowser

import macaroons
import requests


def deserialize(json_macaroon):
    '''Deserialize a JSON macaroon into a macaroon object.

    @param the JSON macaroon to deserialize as a dict.
    @return the deserialized macaroon object.
    '''
    return macaroons.deserialize(to_base64(json_macaroon))


def serialize_macaroon_string(macaroon):
    '''Serialize macaroon object to string.

    @param macaroon object to be serialized.
    @return a string serialization form of the macaroon.
    '''
    return base64.urlsafe_b64decode(
        _add_padding(macaroon.serialize_json()))


def to_base64(json_macaroon):
    '''Base 64 encode a JSON macaroon.

    @param the JSON macaroon as a dict to encode.
    @return the encoded macaroon.
    '''
    return base64.urlsafe_b64encode(json.dumps(json_macaroon))


def _add_padding(s):
    '''Add padding to base64 encoded string
    libmacaroons does not give padded base64 string from serialization.

    @param string s to be padded.
    @return a padded string.
    '''
    return s + '=' * ((4 - (len(s) % 4)) % 4)


class DischargeError(requests.RequestException):
    '''Exception that is been raised by Bakery public methods when a discharge
       error happens.
    '''
    pass


class Bakery(object):
    ''' Bakery is a wrapper around requests that ensures
        that macaroons headers are sent to the server if present or gather the
        discharged macaroons automatically before sending the request.
    '''
    def __init__(self, initial_macaroons=None, discharge_token=None,
                 timeout=30):
        '''
        @param initial_macaroons initial macaroon to be used in headers as a
            base 64 encoded array of base64 encoded json(dict) macaroons.
        @param discharge_token initial discharge token
            as a base64 encoded json (dict) macaroon.
        @param timeout timeout for wait url.
        '''
        self._macaroons = initial_macaroons
        self._discharge_token = discharge_token
        self._timeout = timeout

    def get(self, url, **kwargs):
        '''Act as the same than requests.get, same arguments,
           same returned value, same exception raised except DischargeError
           when something wrong happened when discharging.
           If macaroons are present, the headers will be augmented with it.
        '''
        if self._macaroons is not None:
            headers = kwargs.setdefault('headers', {})
            headers.update({
                'Bakery-Protocol-Version': 1,
                'Macaroons': self._macaroons,
            })
        response = requests.get(url, **kwargs)
        if (response.status_code == 401 and
                response.headers['Www-Authenticate'] == 'Macaroon') \
                or response.status_code == 407:
            try:
                response_json = response.json()
            except ValueError:
                raise DischargeError(
                    'Unable to get data from unauthorized response')
            try:
                code = response_json['Code']
            except KeyError:
                raise DischargeError(
                    'code not found in unauthorized response {}'.format(
                        response.content))
            if code != 'macaroon discharge required':
                raise DischargeError(
                    'Unknown code found in unauthorized response {}'.format(
                        code))
            try:
                serialized_macaroon = response_json['Info']['Macaroon']
            except KeyError:
                raise DischargeError(
                    'macaroon not found in unauthorized response {}'.format(
                        response.content))
            macaroon = deserialize(serialized_macaroon)
            discharges = self._discharge(macaroon)
            encoded_discharges = map(serialize_macaroon_string, discharges)
            self._macaroons = base64.urlsafe_b64encode(
                '[' + ','.join(encoded_discharges) + ']')
            return self.get(url, **kwargs)

        return response

    def _discharge(self, macaroon):
        '''Discharge a macaroon.

        @param the macaroon object to discharge.
        @returns the discharged macaroons as an array of macaroon object.
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
        if self._discharge_token is not None:
            headers['Macaroons'] = self._discharge_token
        payload = {'id': condition, 'location': location}

        try:
            response = requests.post(third_party_location + '/discharge',
                                     headers=headers,
                                     data=payload,
                                     timeout=self._timeout)
        except requests.RequestException as exc:
            raise DischargeError(
                'Unable to access discharge endpoint: {}'.format(exc.message))
        if response.status_code == 200:
            return self._extract_macaroon_from_response(response)
        elif response.status_code == 401:
            visit_url, wait_url = self._extract_urls(response)
            # Open a browser so the user can validate its identity.
            webbrowser.open(visit_url, new=1)

            # Wait on the wait url and then get a macaroon if validated.
            return self._acquire_macaroon_from_wait(wait_url)
        else:
            raise DischargeError(
                'Unknown status code from discharge endpoint: {}'.format(
                    response.status_code)
            )

    def _extract_macaroon_from_response(self, response):
        ''' Extarct the macaroon from a direct successful discharge.

        @param response from direct successful discharge.
        @return a macaroon object.
        @raises DischargeError if any error happens.
        '''
        try:
            response_json = response.json()
        except ValueError:
            raise DischargeError(
                'Unable to access data from discharge endpoint on 200')
        try:
            return deserialize(response_json['Macaroon'])
        except KeyError:
            raise DischargeError(
                'Unable to access macaroon from discharge endpoint on 200')

    def _acquire_macaroon_from_wait(self, wait_url):
        ''' Wait that the user did validate its identity as the get will block
            until then.
            If validated then we get the macaroon from the wait endpoint
            response.

        @param wait_url the get url to call to get a macaroon.
        @return a macaroon object
        @raises DischargeError if any error happens.
        '''

        try:
            resp = requests.get(wait_url, timeout=self._timeout)
        except requests.RequestException as exc:
            raise DischargeError(
                'Unable to access wait url: {}'.format(exc.message))
        if not resp.ok:
            raise DischargeError(
                'Unexpected status code from wait url: {}'.format(
                    resp.status_code
                ))
        try:
            response_json = resp.json()
        except ValueError:
            raise DischargeError(
                'Unable to access json macaroon from wait url'
            )
        try:
            discharge_token = response_json['DischargeToken']
            macaroon = response_json['Macaroon']
        except KeyError:
            raise DischargeError(
                'Unable to access macaroon or discharge token from'
                ' discharge endpoint'
            )
        if self._discharge_token is None:
            self._discharge_token = to_base64(discharge_token)
        return deserialize(macaroon)

    def _extract_urls(self, response):
        ''' Return the visit and wait URL from response.

        @param response the response from the discharge endpoint.
        @return the visit and wait URL.
        @raises DischargeError for ant error during the process response.
        '''
        try:
            response_json = response.json()
        except ValueError:
            raise DischargeError(
                'Unable to access json from discharge endpoint on 401')
        try:
            code = response_json['Code']
        except KeyError:
            raise DischargeError(
                'Unable to access code from discharge endpoint on 401')
        if code != 'interaction required':
            raise DischargeError(
                'Unexpected Code on discharge endpoint: {}'.format(
                    response_json['Code']))
        try:
            visit_url = response_json['Info']['VisitURL']
            wait_url = response_json['Info']['WaitURL']
        except KeyError:
            raise DischargeError(
                'Unable to access wait or visit url from discharge '
                'endpoint on 401')
        return visit_url, wait_url
