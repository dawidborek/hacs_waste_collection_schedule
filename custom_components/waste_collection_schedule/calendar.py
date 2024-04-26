"""Calendar platform support for Waste Collection Schedule."""

import logging
from datetime import datetime, timedelta

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant, callback
from .const import DOMAIN, CONF_SOURCE_NAME, CONF_SOURCE_ARGS, CONF_SOURCE_CALENDAR_TITLE, CONF_SEPARATOR, CONF_SEPARATOR_DEFAULT, CONF_RANDOM_FETCH_TIME_OFFSET, CONF_RANDOM_FETCH_TIME_OFFSET_DEFAULT, CONF_FETCH_TIME, CONF_FETCH_TIME_DEFAULT, CONF_DAY_SWITCH_TIME, CONF_DAY_SWITCH_TIME_DEFAULT
from waste_collection_schedule import SourceShell
import homeassistant.helpers.config_validation as cv
from .init_yaml import WasteCollectionApi

# fmt: off
from custom_components.waste_collection_schedule.waste_collection_schedule.collection_aggregator import \
    CollectionAggregator
from custom_components.waste_collection_schedule.waste_collection_schedule.source_shell import \
    SourceShell

# fmt: on

_LOGGER = logging.getLogger(__name__)

# Config flow setup
async def async_setup_entry(hass, config, async_add_entities):
    coordinator = hass.data[DOMAIN][config.entry_id]
    shell = coordinator.shell

    entities = [
        WasteCollectionCalendar(
            coordinator=coordinator,
            aggregator=CollectionAggregator([shell]),
            name=shell.calendar_title,
            unique_id=calc_unique_calendar_id(shell),
        )
    ]

    async_add_entities(entities, update_before_add=True)

# YAML setup
async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up calendar platform."""
    # We only want this platform to be set up via discovery.
    if discovery_info is None:
        return

    entities = []

    api = discovery_info["api"]

    for shell in api.shells:
        dedicated_calendar_types = shell.get_dedicated_calendar_types()
        for type in dedicated_calendar_types:
            entities.append(
                WasteCollectionCalendar(
                    api=api,
                    aggregator=CollectionAggregator([shell]),
                    name=shell.get_calendar_title_for_type(type),
                    include_types={shell.get_collection_type_name(type)},
                    unique_id=calc_unique_calendar_id(shell, type),
                )
            )

        entities.append(
            WasteCollectionCalendar(
                api=api,
                aggregator=CollectionAggregator([shell]),
                name=shell.calendar_title,
                exclude_types={
                    shell.get_collection_type_name(type)
                    for type in dedicated_calendar_types
                },
                unique_id=calc_unique_calendar_id(shell),
            )
        )

    async_add_entities(entities)


class WasteCollectionCalendar(CalendarEntity):
    """Calendar entity class."""

    def __init__(
        self,
        aggregator,
        name,
        unique_id: str,
        coordinator=None,
        api=None,
        include_types=None,
        exclude_types=None,
    ):
        self._api = api
        self._coordinator = coordinator
        self._aggregator = aggregator
        self._name = name
        self._include_types = include_types
        self._exclude_types = exclude_types
        self._unique_id = unique_id
        self._attr_unique_id = unique_id
        
        if coordinator:
            self._attr_device_info = coordinator.device_info

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()

        if self._coordinator:
            self.async_on_remove(
                self._coordinator.async_add_listener(
                    self._handle_coordinator_update, None
                )
            )
    
    @callback
    def _handle_coordinator_update(self) -> None:
        self.async_write_ha_state()

    @property
    def name(self):
        """Return entity name."""
        return self._name

    @property
    def event(self):
        """Return next collection event."""
        collections = self._aggregator.get_upcoming(
            count=1,
            include_today=True,
            include_types=self._include_types,
            exclude_types=self._exclude_types,
        )

        if len(collections) == 0:
            return None
        else:
            return self._convert(collections[0])

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ):
        """Return all events within specified time span."""
        events = []

        for collection in self._aggregator.get_upcoming(
            include_today=True,
            include_types=self._include_types,
            exclude_types=self._exclude_types,
        ):
            event = self._convert(collection)

            if start_date <= event.start_datetime_local <= end_date:
                events.append(event)

        return events

    def _convert(self, collection) -> CalendarEvent:
        """Convert an collection into a Home Assistant calendar event."""
        return CalendarEvent(
            summary=collection.type,
            start=collection.date,
            end=collection.date + timedelta(days=1),
        )


def calc_unique_calendar_id(shell: SourceShell, type: str = None):
    return shell.unique_id + ("_" + type if type is not None else "") + "_calendar"
