import json

from DIRAC import gLogger
from DIRAC.Core.Utilities.SitesDIRACGOCDBmapping import getGOCSiteName, getDIRACSiteName
from DIRAC.Core.Utilities.SiteSEMapping import getSEsForSite
from DIRAC.Core.Utilities.Plotting.FileCoding import codeRequestInFileId
from DIRAC.ResourceStatusSystem.Utilities.CSHelpers import getSiteComputingElements
from DIRAC.ResourceStatusSystem.Client.PublisherClient import PublisherClient

from WebAppDIRAC.Lib.WebHandler import asyncGen
from WebAppDIRAC.WebApp.handler.ResourceSummaryHandler import ResourceSummaryHandler

ELEMENT_TYPE = 'Site'


class SiteSummaryHandler(ResourceSummaryHandler):

  AUTH_PROPS = "all"

  @asyncGen
  def web_getSiteSummaryData(self):
    '''This method returns the data required to fill the grid.'''
    requestParams = self.__requestParams()
    gLogger.info(requestParams)

    pub = PublisherClient()

    elementStatuses = yield self.threadTask(pub.getElementStatuses, 'Site',
                                            requestParams['name'],
                                            requestParams['elementType'],
                                            requestParams['statusType'],
                                            requestParams['status'],
                                            requestParams['tokenOwner'])
    if not elementStatuses['OK']:
      self.finish({'success': 'false', 'error': elementStatuses['Message']})

    elementList = [dict(zip(elementStatuses['Columns'], site)) for site in elementStatuses['Value']]

    for elementStatus in elementList:

      elementStatus['Country'] = elementStatus['Name'][-2:]
      elementStatus['DateEffective'] = str(elementStatus['DateEffective'])
      elementStatus['LastCheckTime'] = str(elementStatus['LastCheckTime'])
      elementStatus['TokenExpiration'] = str(elementStatus['TokenExpiration'])

    result = {'success': 'true', 'result': elementList, 'total': len(elementList)}

    self.finish(result)

  def _getInfo(self, requestParams):

    gLogger.info(requestParams)

    if not requestParams['name']:
      gLogger.warn('No name given')
      self.finish({'success': 'false', 'error': 'We need a Site Name to generate an Overview'})

    elementName = requestParams['name'][0]

    pub = PublisherClient()

    elementStatuses = pub.getElementStatuses('Site',
                                             str(elementName),
                                             None,
                                             'all',
                                             None,
                                             None)

    if not elementStatuses['OK']:
      gLogger.error(elementStatuses['Message'])
      self.finish({'success': 'false', 'error': 'Error getting ElementStatus information'})

    if not elementStatuses['Value']:
      gLogger.error('element "%s" not found' % elementName)
      self.finish({'success': 'false', 'error': 'element "%s" not found' % elementName})

    elementStatus = [dict(zip(elementStatuses['Columns'], element)) for element in elementStatuses['Value']][0]
    elementStatus['DateEffective'] = str(elementStatus['DateEffective'])
    elementStatus['LastCheckTime'] = str(elementStatus['LastCheckTime'])
    elementStatus['TokenExpiration'] = str(elementStatus['TokenExpiration'])

    gocdb_name = getGOCSiteName(elementName)
    if not gocdb_name['OK']:
      gLogger.error(gocdb_name['Message'])
      elementStatus['GOCDB'] = ""
      gocdb_name = ''
    else:
      gocdb_name = gocdb_name['Value']
      elementStatus['GOCDB'] = '<a href="https://goc.egi.eu/portal/index.php?Page_'
      elementStatus['GOCDB'] += 'Type=Submit_Search&SearchString=%s" target="_blank">%s</a>' % (
          gocdb_name, gocdb_name)

    dirac_names = getDIRACSiteName(gocdb_name)
    if not dirac_names['OK']:
      gLogger.error(dirac_names['Message'])
      dirac_names = []
    else:
      elementStatus['GOCDB'] += "("
      for i in dirac_names['Value']:
        elementStatus['GOCDB'] += "%s " % i
      elementStatus['GOCDB'] += ")"

    elementStatus["GGUS"] = '<a href="https://ggus.eu/ws/ticket_search.php?'
    elementStatus["GGUS"] += 'show_columns_check[]=REQUEST_ID&'
    elementStatus["GGUS"] += 'show_columns_check[]=TICKET_TYPE&show_columns_check[]=AFFECTED_VO&'
    elementStatus["GGUS"] += 'show_columns_check[]=AFFECTED_SITE&show_columns_check[]=PRIORITY'
    elementStatus["GGUS"] += '&show_columns_check[]=RESPONSIBLE_UNIT&'
    elementStatus["GGUS"] += 'show_columns_check[]=STATUS&show_columns_check[]=DATE_OF_CREATION&'
    elementStatus["GGUS"] += 'show_columns_check[]=LAST_UPDATE&show_columns_check[]=TYPE_OF_PROBLEM&'
    elementStatus["GGUS"] += 'show_columns_check[]=SUBJECT&ticket=&supportunit=all&su_hierarchy=all&'
    elementStatus["GGUS"] += 'vo=all&user=&keyword=&involvedsupporter=&assignto=&'
    elementStatus["GGUS"] += 'affectedsite=%s&specattrib=0&status=open&priority=all&'
    elementStatus["GGUS"] += 'typeofproblem=all&ticketcategory=&mouarea=&technology_provider=&'
    elementStatus["GGUS"] += 'date_type=creation+date&radiotf=1&timeframe=any&from_date=&to_date=&' % gocdb_name
    elementStatus["GGUS"] += 'untouched_date=&orderticketsby=GHD_INT_REQUEST_ID&'
    elementStatus["GGUS"] += 'orderhow=descending" target="_blank"> %s tickets</a>' % gocdb_name

    convertName = {'CERN-PROD': 'CERN',
                   'INFN-T1': 'CNAF',
                   'FZK-LCG2': 'GridKa',
                   'IN2P3-CC': 'IN2P3',
                   'NIKHEF-ELPROD': 'NIKHEF',
                   'pic': 'PIC',
                   'RAL-LCG2': 'RAL',
                   'SARA-MATRIX': 'SARA'}

    elog = convertName.get(gocdb_name, "")

    elementStatus['Elog'] = '<a href="https://lblogbook.cern.ch/Operations/?Site=^' + \
        elog + '%24&mode=summary" target="_blank">' + elog + '</a>'

    return {'success': 'true', 'result': elementStatus, 'total': len(elementStatus)}

  def _getStorages(self, requestParams):

    if not requestParams['name']:
      gLogger.warn('No name given')
      return {'success': 'false', 'error': 'We need a Site Name to generate an Overview'}

    pub = PublisherClient()

    elementName = requestParams['name'][0]
    storageElements = getSEsForSite(elementName)
    storageElementsStatus = []
    gLogger.info('storageElements = ' + str(storageElements))

    # FIXME: use properly RSS
    for se in storageElements:
      sestatuses = pub.getElementStatuses('Resource',
                                          se,
                                          None,
                                          None,
                                          None,
                                          None)

      for sestatus in sestatuses['Value']:
        storageElementsStatus.append([sestatus[0], sestatus[2], sestatus[6]])

    return {'success': 'true', 'result': storageElementsStatus, 'total': len(storageElementsStatus)}

  def _getComputingElements(self, requestParams):

    if not requestParams['name']:
      gLogger.warn('No name given')
      return {'success': 'false', 'error': 'We need a Site Name to generate an Overview'}

    pub = PublisherClient()

    elementName = requestParams['name'][0]

    computing_elements = getSiteComputingElements(elementName)
    computing_elements_status = []
    gLogger.info('computing_elements = ' + str(computing_elements))

    for ce in computing_elements:
      cestatuses = pub.getElementStatuses('Resource',
                                          ce,
                                          None,
                                          'all',
                                          None,
                                          None)
      gLogger.info('cestatus = ' + str(cestatuses))

      for cestatus in cestatuses['Value']:
        computing_elements_status.append([cestatus[0], cestatus[2], cestatus[6]])

    return {'success': 'true', 'result': computing_elements_status, 'total': len(computing_elements_status)}

  def _getImages(self, requestParams):

    if not requestParams['name']:
      gLogger.warn('No name given')
      return {'success': 'false', 'error': 'We need a Site Name to generate an Overview'}

    elementName = requestParams['name'][0]
    pub = PublisherClient()

    elementStatuses = pub.getElementStatuses('Site',
                                             str(elementName),
                                             None,
                                             'all',
                                             None,
                                             None)

    if not elementStatuses['Value']:
      gLogger.error('element "%s" not found' % elementName)
      return {'success': 'false', 'error': 'element "%s" not found' % elementName}

    elementStatus = [dict(zip(elementStatuses['Columns'], element)) for element in elementStatuses['Value']][0]

    plotDict1 = self.getPlotDict(elementStatus['Name'], 'FinalMajorStatus',
                                 'RunningJobs', 'Job', plotTitle='Final Minor Status of jobs')
    image1 = codeRequestInFileId(plotDict1)['Value']['plot']

    plotDict2 = self.getPlotDict(elementStatus['Name'], 'GridStatus',
                                 'NumberOfPilots', 'Pilot')
    image2 = codeRequestInFileId(plotDict2)['Value']['plot']

    plotDict3 = self.getPlotDict(elementStatus['Name'], 'JobType',
                                 'RunningJobs', 'Job', plotTitle='Jobs by job type')
    image3 = codeRequestInFileId(plotDict3)['Value']['plot']

    plotDict4 = self.getPlotDict(elementStatus['Name'], 'JobSplitType',
                                 'NumberOfJobs', 'WMSHistory', status='Running')
    image4 = codeRequestInFileId(plotDict4)['Value']['plot']

    plotDict5 = self.getPlotDict(elementStatus['Name'], 'Channel',
                                 'SuceededTransfers', 'DataOperation')
    image5 = codeRequestInFileId(plotDict5)['Value']['plot']

    plotDict6 = self.getPlotDict(elementStatus['Name'], 'FinalStatus',
                                 'FailedTransfers', 'DataOperation')
    image6 = codeRequestInFileId(plotDict6)['Value']['plot']

    return {'success': 'true', 'result': [image1, image2, image3, image4, image5, image6], 'total': 6}

  def getPlotDict(self, siteName, grouping, reportName, typeName,
                  plotTitle=None,
                  status=None):

    plotDict = {'condDict': {
        'Site': [siteName],
        'grouping': [grouping]
    },
        'extraArgs': {
        'lastSeconds': 43200
    },
        'grouping': grouping,
        'reportName': reportName,
        'typeName': typeName,
        '_plotTitle': plotTitle}

    if plotTitle is not None:
      plotDict['extraArgs']['plotTitle'] = plotTitle
    if status is not None:
      plotDict['condDict']['Status'] = status

    return plotDict

  def __requestParams(self):
    '''
      We receive the request and we parse it, in this case, we are doing nothing,
      but it can be certainly more complex.
    '''

    gLogger.always("!!!  PARAMS: ", str(self.request.arguments))

    responseParams = {
        'name': None,
        'elementType': None,
        'statusType': None,
        'status': None,
        'action': None,
        'tokenOwner': None
    }

    for key in responseParams:
      if key in self.request.arguments and str(self.request.arguments[key][-1]):
        responseParams[key] = list(json.loads(self.request.arguments[key][-1]))

    return responseParams
