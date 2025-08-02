# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

"""This module describes base classes for classads and advertisers."""

import os
import time

from . import condorManager, logSupport

###############################################################################
# Generic Classad Structure
###############################################################################


class Classad:
    """Base class describing a classad."""

    def __init__(self, adType, advertiseCmd, invalidateCmd):
        """Constructor.

        Args:
            adType (str): Type of the classad.
            advertiseCmd (str): Condor update-command to advertise this classad.
            invalidateCmd (str): Condor update-command to invalidate this classad.
        """
        self.adType = adType
        self.adAdvertiseCmd = advertiseCmd
        self.adInvalidateCmd = invalidateCmd

        self.adParams = {}
        """
        try:
            self.adParams
        except Exception:
            self.adParams = {}
        """
        self.adParams["MyType"] = self.adType
        self.adParams["GlideinMyType"] = self.adType
        self.adParams["GlideinWMSVersion"] = "UNKNOWN"

    def update(self, params_dict, prefix=""):
        """Update or add ClassAd attributes.

        Args:
            params_dict (dict): New attributes.
            prefix (str): Prefix used for the attribute names. Defaults to "".
        """
        for k, v in list(params_dict.items()):
            if isinstance(v, int):
                # don't quote ints
                self.adParams[f"{prefix}{k}"] = v
            else:
                escaped_v = str(v).replace("\n", "\\n")
                self.adParams[f"{prefix}{k}"] = "%s" % escaped_v

    def writeToFile(self, filename, append=True):
        """Write a ClassAd to a file, adding a blank line if in append mode to separate the ClassAd.

        There can be no empty line at the beginning of the file:
        https://htcondor-wiki.cs.wisc.edu/index.cgi/tktview?tn=5147

        Args:
            filename (str): File to write to.
            append (bool): Write mode if False, append if True. Defaults to True.
        """
        o_flag = "a"
        if not append:
            o_flag = "w"

        try:
            f = open(filename, o_flag)
        except Exception as e:
            raise e

        with f:
            if append and f.tell() > 0:
                # Write empty line when in append mode to be considered a separate classad
                # Skip at the beginning of the file (HTCondor bug #5147)
                # (one or more empty lines separate multiple classads on the same file)
                f.write("\n")
            f.write("%s" % self)

    def __str__(self):
        """String representation of the classad.

        Returns:
            str: The string representation of the classad.
        """
        ad = ""

        for key, value in self.adParams.items():
            if isinstance(value, str):
                # Format according to Condor String Literal definition
                # http://research.cs.wisc.edu/htcondor/manual/v7.8/4_1HTCondor_s_ClassAd.html#SECTION005121
                classad_value = value.replace('"', r"\"")
                ad += f'{key} = "{classad_value}"\n'
            else:
                ad += f"{key} = {value}\n"
        return ad


###############################################################################
# Generic Classad Advertiser
###############################################################################


class ClassadAdvertiser:
    """
    Base Class to handle the advertisement of classads to condor pools.
    It contains a dictionary of classads keyed by the classad name and
    functions to do advertisement and invalidation of classads
    """

    def __init__(self, pool=None, multi_support=False, tcp_support=False):
        """
        Constructor

        @type pool: string
        @param pool: Collector address
        @type multi_support: bool
        @param multi_support: True if the installation support advertising multiple classads with one condor_advertise command. Defaults to False.
        """

        # Dictionary of classad objects
        self.classads = {}
        self.pool = pool
        self.multiAdvertiseSupport = multi_support
        self.multiClassadDelimiter = "\n"
        self.tcpAdvertiseSupport = tcp_support

        # Following data members should be overridden.
        # Use generic defaults here.
        self.adType = "glideclassad"
        self.adAdvertiseCmd = "UPDATE_AD_GENERIC"
        self.adInvalidateCmd = "INVALIDATE_ADS_GENERIC"
        # gcs_ac = glide-classad-support_advertise-classad
        self.advertiseFilePrefix = "gcs_ac"

    def addClassad(self, name, ad_obj):
        """
        Adds the classad to the classad dictionary

        @type name: string
        @param name: Name of the classad
        @type ad_obj: ClassAd
        @param ad_obj: Actual classad object
        """

        self.classads[name] = ad_obj

    def classadToFile(self, ad):
        """
        Write classad to the file and return the filename

        @type ad: string
        @param ad: Name of the classad

        @rtype: string
        @return: Name of the file
        """

        fname = self.getUniqClassadFilename()

        try:
            with open(fname, "w") as fd:
                fd.write("%s" % self.classads[ad])
        except Exception:
            logSupport.log.error("Error creating a classad file %s" % fname)
            return ""

        return fname

    def classadsToFile(self, ads):
        """
        Write multiple classads to a file and return the filename.
        Use only when multi advertise is supported by condor.

        @type ads: list
        @param ads: Classad names

        @rtype: string
        @return: Filename containing all the classads to advertise
        """

        fname = self.getUniqClassadFilename()

        try:
            with open(fname, "w") as fd:
                for ad in ads:
                    fd.write("%s" % self.classads[ad])
                    # Condor uses an empty line as classad delimiter
                    # Append an empty line for advertising multiple classads
                    fd.write(self.multiClassadDelimiter)
        except Exception:
            logSupport.log.error("Error creating a classad file %s" % fname)
            return ""

        return fname

    def doAdvertise(self, fname):
        """
        Do the actual advertisement of classad(s) in the file

        @type fname: string
        @param fname: File name containing classad(s)
        """

        if (fname) and (fname != ""):
            try:
                exe_condor_advertise(
                    fname,
                    self.adAdvertiseCmd,
                    self.pool,
                    is_multi=self.multiAdvertiseSupport,
                    use_tcp=self.tcpAdvertiseSupport,
                )
            finally:
                os.remove(fname)
        else:
            raise RuntimeError("Failed advertising %s classads" % self.adType)

    def advertiseClassads(self, ads=None):
        """
        Advertise multiple classads to the pool

        @type ads: list
        @param ads: classad names to advertise
        """

        if (ads is None) or (len(ads) == 0):
            logSupport.log.info("There are 0 classads to advertise")
            return

        logSupport.log.info("There are %i classads to advertise" % len(ads))

        if self.multiAdvertiseSupport:
            fname = self.classadsToFile(ads)
            self.doAdvertise(fname)
        else:
            # There is no multi advertise support.
            # Advertise one classad at a time.
            for ad in ads:
                self.advertiseClassad(ad)

    def advertiseClassad(self, ad):
        """
        Advertise the classad to the pool

        @type ad: string
        @param ad: Name of the classad
        """

        fname = self.classadToFile(ad)
        self.doAdvertise(fname)

    def advertiseAllClassads(self):
        """
        Advertise all the known classads to the pool
        """

        self.advertiseClassads(list(self.classads.keys()))

    def invalidateClassad(self, ad):
        """
        Invalidate the classad from the pool

        @type type: string
        @param type: Name of the classad
        """

        self.invalidateConstrainedClassads('Name == "%s"' % ad)

    def invalidateAllClassads(self):
        """
        Invalidate all the known classads
        """

        for ad in list(self.classads.keys()):
            self.invalidateClassad(ad)

    def invalidateConstrainedClassads(self, constraint):
        """
        Invalidate classads from the pool matching the given constraints

        @type type: string
        @param type: Condor constraints for filtering the classads
        """

        try:
            fname = self.getUniqClassadFilename()
            with open(fname, "w") as fd:
                fd.write('MyType = "Query"\n')
                fd.write('TargetType = "%s"\n' % self.adType)
                fd.write("Requirements = %s" % constraint)

            exe_condor_advertise(
                fname,
                self.adInvalidateCmd,
                self.pool,
                is_multi=self.multiAdvertiseSupport,
                use_tcp=self.tcpAdvertiseSupport,
            )
        finally:
            if fd:
                os.remove(fname)
            else:
                logSupport.log.error("Error creating a classad file %s" % fname)

    def getAllClassads(self):
        """
        Return all the known classads

        @rtype: string
        @return: All the known classads delimited by empty line
        """

        ads = ""

        for ad in list(self.classads.keys()):
            ads = f"{ads}{self.classads[ad]}\n"
        return ads

    def getUniqClassadFilename(self):
        """
        Return a uniq file name for advertising/invalidating classads

        @rtype: string
        @return: Filename
        """

        return generate_classad_filename(prefix=self.advertiseFilePrefix)


###############################################################################
# Generic Utility Functions used with classads
###############################################################################


def generate_classad_filename(prefix="gwms_classad"):
    """
    Return a uniq file name for advertising/invalidating classads

    @type prefix: string
    @param prefix: Prefix to be used for the filename

    @rtype: string
    @return: Filename
    """

    # Get a 9 digit number that will stay 9 digit for next 25 years
    short_time = time.time() - 1.05e9
    fname = "/tmp/%s_%li_%li" % (prefix, short_time, os.getpid())

    return fname


############################################################
#
# I N T E R N A L - Do not use
#
############################################################


def exe_condor_advertise(fname, command, pool, is_multi=False, use_tcp=False):
    """
    Wrapper to execute condorAdvertise from the condorManager
    """

    logSupport.log.debug(f"CONDOR ADVERTISE {fname} {command} {pool} {is_multi} {use_tcp}")
    return condorManager.condorAdvertise(fname, command, use_tcp, is_multi, pool)
