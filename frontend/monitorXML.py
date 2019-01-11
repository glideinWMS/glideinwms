import copy
import time, os
from glideinwms.frontend.glideinFrontendMonitoring import Monitoring_Output, tmp2final
from glideinwms.lib import logSupport
from glideinwms.lib import xmlFormat

# Default Configuration
DEFAULT_CONFIG = {"name": "monitorXML"}

DEFAULT_CONFIG_AGGR = {}


# noinspection PyRedeclaration
class Monitoring_Output(Monitoring_Output):
    def __init__(self, config, configAgg):
        # Get Default Config from Parent
        super(Monitoring_Output, self).__init__()

        # Set Default Config for this Child
        for key in DEFAULT_CONFIG:
            self.config[key] = DEFAULT_CONFIG[key]

        for key in DEFAULT_CONFIG_AGGR:
            self.configAggr[key] = DEFAULT_CONFIG_AGGR[key]

        # Set Config from Pass Parameters (from the Frontend XML Config File)
        for key in config:
            self.config[key] = config[key]

        for key in configAgg:
            self.configAggr[key] = configAgg[key]

        # Group Stats
        self.files_updatedGroupStats = None

        # Factory Stats
        self.updatedFactoryStats = time.time()
        self.files_updatedFactoryStats = None

    def write_groupStats(self, total, factories_data, states_data, updated):
        # write snaphot file
        xml_str=('<?xml version="1.0" encoding="ISO-8859-1"?>\n\n'+
                 '<VOFrontendGroupStats>\n'+
                 self.get_xml_GroupStats_updated(indent_tab=xmlFormat.DEFAULT_TAB, leading_tab=xmlFormat.DEFAULT_TAB, updated=updated)+"\n"+
                 self.get_xml_GroupStats_factories_data(indent_tab=xmlFormat.DEFAULT_TAB, leading_tab=xmlFormat.DEFAULT_TAB, data=factories_data)+"\n"+
                 self.get_xml_GroupStats_states_data(indent_tab=xmlFormat.DEFAULT_TAB, leading_tab=xmlFormat.DEFAULT_TAB, data=states_data)+"\n"+
                 self.get_xml_GroupStats_total(indent_tab=xmlFormat.DEFAULT_TAB, leading_tab=xmlFormat.DEFAULT_TAB, total=total)+"\n"+
                 "</VOFrontendGroupStats>\n")

        Monitoring_Output.write_file("frontend_status.xml", xml_str)

    def write_factoryStats(self, data, total_el, updated):
        # write snaphot file
        xml_str=('<?xml version="1.0" encoding="ISO-8859-1"?>\n\n'+
                 '<glideFactoryEntryQStats>\n'+
                 self.get_xml_FactoryStats_updated(indent_tab=xmlFormat.DEFAULT_TAB, leading_tab=xmlFormat.DEFAULT_TAB, updated=updated)+"\n"+
                 self.get_xml_FactoryStats_data(indent_tab=xmlFormat.DEFAULT_TAB, leading_tab=xmlFormat.DEFAULT_TAB, data=data)+"\n"+
                 self.get_xml_FactoryStats_total(indent_tab=xmlFormat.DEFAULT_TAB, leading_tab=xmlFormat.DEFAULT_TAB, total=total_el)+"\n"+
                 "</glideFactoryEntryQStats>\n")
        Monitoring_Output.write_file("schedd_status.xml", xml_str)

    def write_aggregation(self, global_fact_totals, updated, global_total, status):
        xml_str = ('<?xml version="1.0" encoding="ISO-8859-1"?>\n\n' +
                   '<VOFrontendStats>\n' +
                   xmlFormat.time2xml(updated, "updated", indent_tab=xmlFormat.DEFAULT_TAB,
                                      leading_tab=xmlFormat.DEFAULT_TAB) + "\n" +
                   xmlFormat.dict2string(status["groups"], dict_name="groups", el_name="group",
                                         subtypes_params={"class": {"dicts_params": {"factories": {"el_name": "factory",
                                                                                                   "subtypes_params": {
                                                                                                       "class": {
                                                                                                           "subclass_params": {
                                                                                                               "Requested": {
                                                                                                                   "dicts_params": {
                                                                                                                       "Parameters": {
                                                                                                                           "el_name": "Parameter",
                                                                                                                           "subtypes_params": {
                                                                                                                               "class": {}}}}}}}}},
                                                                                     "states": {"el_name": "state",
                                                                                                "subtypes_params": {
                                                                                                    "class": {
                                                                                                        "subclass_params": {
                                                                                                            "Requested": {
                                                                                                                "dicts_params": {
                                                                                                                    "Parameters": {
                                                                                                                        "el_name": "Parameter",
                                                                                                                        "subtypes_params": {
                                                                                                                            "class": {}}}}}}}}}
                                                                                     }}},
                                         leading_tab=xmlFormat.DEFAULT_TAB) + "\n" +
                   xmlFormat.class2string(status["total"], inst_name="total",
                                          leading_tab=xmlFormat.DEFAULT_TAB) + "\n" +

                   xmlFormat.dict2string(global_fact_totals['factories'], dict_name="factories", el_name="factory",
                                         subtypes_params={"class": {"subclass_params": {
                                             "Requested": {"dicts_params": {"Parameters": {"el_name": "Parameter",

                                                                                           "subtypes_params": {
                                                                                               "class": {}}}}}}}},
                                         leading_tab=xmlFormat.DEFAULT_TAB) + "\n" +
                   xmlFormat.dict2string(global_fact_totals['states'], dict_name="states", el_name="state",
                                         subtypes_params={"class": {"subclass_params": {
                                             "Requested": {"dicts_params": {"Parameters": {"el_name": "Parameter",

                                                                                           "subtypes_params": {
                                                                                               "class": {}}}}}}}},
                                         leading_tab=xmlFormat.DEFAULT_TAB) + "\n" +
                   "</VOFrontendStats>\n")

        Monitoring_Output.write_file(Monitoring_Output.global_config_aggr["status_relname"], xml_str)

    # Internal Functions

    # Group Stats

    def get_xml_GroupStats_factories_data(self,indent_tab=xmlFormat.DEFAULT_TAB,leading_tab="", data=None):
        return xmlFormat.dict2string(data,
                                     dict_name='factories', el_name='factory',
                                     subtypes_params={"class":{'subclass_params':{'Requested':{'dicts_params':{'Parameters':{'el_name':'Parameter'}}}}}},
                                       indent_tab=indent_tab, leading_tab=leading_tab)

    def get_xml_GroupStats_states_data(self,indent_tab=xmlFormat.DEFAULT_TAB,leading_tab="", data=None):
        return xmlFormat.dict2string(data,
                                     dict_name='states', el_name='state',
                                     subtypes_params={"class":{'subclass_params':{'Requested':{'dicts_params':{'Parameters':{'el_name':'Parameter'}}}}}},
                                       indent_tab=indent_tab, leading_tab=leading_tab)

    def get_xml_GroupStats_updated(self,indent_tab=xmlFormat.DEFAULT_TAB,leading_tab="",updated=None):
        return xmlFormat.time2xml(updated, "updated", indent_tab=xmlFormat.DEFAULT_TAB, leading_tab="")

    def get_xml_GroupStats_total(self,indent_tab=xmlFormat.DEFAULT_TAB,leading_tab="", total=None):
        return xmlFormat.class2string(total,
                                      inst_name="total",
                                      indent_tab=indent_tab, leading_tab=leading_tab)

    # Factory Stats

    def get_xml_FactoryStats_data(self,indent_tab=xmlFormat.DEFAULT_TAB,leading_tab="", data=None):
        return xmlFormat.dict2string(data,
                                     dict_name="frontends", el_name="frontend",
                                     subtypes_params={"class":{'subclass_params':{'Requested':{'dicts_params':{'Parameters':{'el_name':'Parameter'}}}}}},
                                     indent_tab=indent_tab, leading_tab=leading_tab)

    def get_xml_FactoryStats_total(self,indent_tab=xmlFormat.DEFAULT_TAB,leading_tab="", total=None):
        return xmlFormat.class2string(total,
                                      inst_name="total",
                                      indent_tab=indent_tab, leading_tab=leading_tab)

    def get_xml_FactoryStats_updated(self,indent_tab=xmlFormat.DEFAULT_TAB,leading_tab="", updated=None):
        return xmlFormat.time2xml(updated, "updated", indent_tab=xmlFormat.DEFAULT_TAB, leading_tab="")

    # Aggregation

