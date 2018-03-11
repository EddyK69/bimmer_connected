"""Models the state of a vehicle."""

import datetime
import logging
from enum import Enum
from typing import List

from bimmer_connected.const import VEHICLE_STATUS_URL

_LOGGER = logging.getLogger(__name__)


LIDS = ['doorDriverFront', 'doorPassengerFront', 'doorDriverRear', 'doorPassengerRear',
        'hood', 'trunk']

# figure out what the sunroof is called in this api
WINDOWS = ['windowDriverFront', 'windowPassengerFront', 'windowDriverRear', 'windowPassengerRear']


class LidState(Enum):
    """Possible states of the hatch, trunk, doors, windows, sun roof."""
    CLOSED = 'CLOSED'
    OPEN = 'OPEN'
    INTERMEDIATE = 'INTERMEDIATE'


class LockState(Enum):
    """Possible states of the door locks."""
    LOCKED = 'LOCKED'
    SECURED = 'SECURED'
    SELECTIVELOCKED = 'SELECTIVELOCKED'
    UNLOCKED = 'UNLOCKED'


class ParkingLightState(Enum):
    """Possible states of the parking lights"""
    LEFT = 'LEFT'
    RIGHT = 'RIGHT'
    OFF = 'OFF'


class ConditionBasedServiceStatus(Enum):
    """Status of the condition based services."""
    OK = 'OK'
    OVERDUE = 'OVERDUE'
    PENDING = 'PENDING'


def backend_parameter(func):
    """Decorator for parameters reading data from the backend.

    Errors are handled in a default way.
    """
    def _func_wrapper(self: 'VehicleState', *args, **kwargs):
        # pylint: disable=protected-access
        if self._attributes is None:
            raise ValueError('No data available!')
        try:
            return func(self, *args, **kwargs)
        except KeyError:
            _LOGGER.error('No data available!')
            return None
    return _func_wrapper


class VehicleState(object):  # pylint: disable=too-many-public-methods
    """Models the state of a vehicle."""

    def __init__(self, account, vehicle):
        """Constructor."""
        self._account = account
        self._vehicle = vehicle
        self._attributes = None

    def update_data(self) -> None:
        """Read new status data from the server."""
        _LOGGER.debug('requesting new data from connected drive')

        response = self._account.send_request(
            VEHICLE_STATUS_URL.format(server=self._account.server_url, vin=self._vehicle.vin), logfilename='status')
        attributes = response.json()['vehicleStatus']
        self._attributes = attributes
        _LOGGER.debug('received new data from connected drive')

    @property
    @backend_parameter
    def attributes(self) -> datetime.datetime:
        """Retrieve all attributes from the sever.

        This does not parse the results in any way.
        """
        return self._attributes

    @property
    @backend_parameter
    def timestamp(self) -> datetime.datetime:
        """Get the timestamp when the data was recorded."""
        return self._parse_datetime(self._attributes['updateTime'])

    @property
    @backend_parameter
    def gps_position(self) -> (float, float):
        """Get the last known position of the vehicle.

        Returns a tuple of (latitue, longitude).
        This only provides data, if the vehicle tracking is enabled!
        """
        pos = self._attributes['position']
        if self.is_vehicle_tracking_enabled:
            return float(pos['lat']), float(pos['lon'])
        else:
            _LOGGER.warning('Positioning status of %s is %s', self._vehicle.vin, pos['status'])
        return None

    @property
    @backend_parameter
    def is_vehicle_tracking_enabled(self) -> bool:
        """Check if the position tracking of the vehicle is enabled"""
        return self._attributes['position']['status'] == 'OK'

    @property
    @backend_parameter
    def mileage(self) -> float:
        """Get the mileage of the vehicle.

        Returns a tuple of (value, unit_of_measurement)
        """
        return float(self._attributes['mileage'])

    @property
    @backend_parameter
    def remaining_range_fuel(self) -> float:
        """Get the remaining range of the vehicle on fuel.

        Returns a tuple of (value, unit_of_measurement)
        """
        return float(self._attributes['remainingRangeFuel'])

    @property
    @backend_parameter
    def remaining_fuel(self) -> float:
        """Get the remaining fuel of the vehicle.

        Returns a tuple of (value, unit_of_measurement)
        """
        return float(self._attributes['remainingFuel'])

    @property
    @backend_parameter
    def lids(self) -> List['Lid']:
        """Get all lids (doors+hatch+trunk) of the car."""
        result = []
        for lid in LIDS:
            if lid in self._attributes:
                result.append(Lid(lid, self._attributes[lid]))
        return result

    @property
    def open_lids(self) -> List['Lid']:
        """Get all open lids of the car."""
        return [lid for lid in self.lids if not lid.is_closed]

    @property
    def all_lids_closed(self) -> bool:
        """Check if all lids are closed."""
        return len(list(self.open_lids)) == 0

    @property
    @backend_parameter
    def windows(self) -> List['Window']:
        """Get all windows (doors+sun roof) of the car."""
        result = []
        for lid in WINDOWS:
            if lid in self._attributes:
                result.append(Window(lid, self._attributes[lid]))
        return result

    @property
    def open_windows(self) -> List['Window']:
        """Get all open windows of the car."""
        return [lid for lid in self.windows if not lid.is_closed]

    @property
    def all_windows_closed(self) -> bool:
        """Check if all windows are closed."""
        return len(list(self.open_windows)) == 0

    @property
    @backend_parameter
    def door_lock_state(self) -> LockState:
        """Get state of the door locks."""
        return LockState(self._attributes['doorLockState'])

    @property
    @backend_parameter
    def last_update_reason(self) -> str:
        """The reason for the last state update"""
        return self._attributes['updateReason']

    @property
    @backend_parameter
    def condition_based_services(self) -> List['ConditionBasedServiceReport']:
        """Get staus of the condition based services."""
        return [ConditionBasedServiceReport(s) for s in self._attributes['cbsData']]

    @property
    def are_all_cbs_ok(self) -> bool:
        """Check if the status of all condition based services is "OK"."""
        for cbs in self.condition_based_services:
            if cbs.status != ConditionBasedServiceStatus.OK:
                return False
        return True

    @property
    @backend_parameter
    def parking_lights(self) -> ParkingLightState:
        """Get status of parking lights.

        :returns None if status is unknown.
        """
        return ParkingLightState(self.attributes['parkingLight'])

    @property
    def are_parking_lights_on(self) -> bool:
        """Get status of parking lights.

        :returns None if status is unknown.
        """
        lights = self.parking_lights
        if lights is None:
            return None
        return lights != ParkingLightState.OFF

    @staticmethod
    def _parse_datetime(date_str: str) -> datetime.datetime:
        """Convert a time string into datetime."""
        date_format = "%Y-%m-%dT%H:%M:%S%z"
        return datetime.datetime.strptime(date_str, date_format)


class Lid(object):  # pylint: disable=too-few-public-methods
    """A lid of the vehicle.

    Lids are: Doors + Trunk + Hatch
    """

    def __init__(self, name: str, state: str):
        #: name of the lid
        self.name = name
        #: state of the lid
        self.state = LidState(state)

    @property
    def is_closed(self) -> bool:
        """Check if the lid is closed."""
        return self.state == LidState.CLOSED

    def __str__(self) -> str:
        return '{}: {}'.format(self.name, self.state.value)


class Window(Lid):  # pylint: disable=too-few-public-methods
    """A window of the vehicle.

    A window can be a normal window of the car or the sun roof.
    """
    pass


class ConditionBasedServiceReport(object):  # pylint: disable=too-few-public-methods
    """Entry in the list of condition based services."""

    def __init__(self, data: dict):

        #: date when the service is due
        self.due_date = self._parse_date(data['cbsDueDate'])

        #: status of the service
        self.state = ConditionBasedServiceStatus(data['cbsState'])

        #: service type
        self.service_type = data['cbsType']

        #: distance when the service is due
        self.due_distance = None
        if 'cbsRemainingMileage' in data:
            self.due_distance = int(data['cbsRemainingMileage'])

        #: description of the required service
        self.description = data['cbsDescription']

    @staticmethod
    def _parse_date(datestr: str) -> datetime.datetime:
        formats = [
            '%Y-%m',
            '%m.%Y',
        ]
        for date_format in formats:
            try:
                date = datetime.datetime.strptime(datestr, date_format)
                return date.replace(day=1)
            except ValueError:
                pass
        _LOGGER.error('Unknown time format for CBS: %s', datestr)
        return None
