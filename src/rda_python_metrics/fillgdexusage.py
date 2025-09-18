#!/usr/bin/env python3
#
###############################################################################
#
#     Title : fillgdexusage
#    Author : Zaihua Ji,  zji@ucar.edu
#      Date : 2025-04-14
#   Purpose : python program to retrieve info from GDEX Postgres database for GDS 
#             file accesses and backup fill table tdsusage in PostgreSQL database dssdb.
# 
#    Github : https://github.com/NCAR/rda-python-metrics.git
#
###############################################################################
#
import sys
import re
import glob
from os import path as op
from time import time as tm
from rda_python_common import PgLOG
from rda_python_common import PgUtil
from rda_python_common import PgFile
from rda_python_common import PgDBI
from rda_python_common import PgSplit
from . import PgIPInfo

USAGE = {
   'WEBTBL'  : "wusage",
   'CDATE' : PgUtil.curdate(),
}

DSIDS = {
   "14_schuster" : "d583138",
   "384_duvivier" : "d583139",
   "model_data_for_17_march_2015_storm_event" : "d583140",
   "326_qingyu" : "d583141",
   "354_fasullo" : "d583142",
   "157_gaubert" : "d583143",
   "370_gaubert" : "d583144",
   "459" : "d583145",
   "108_kristenk" : "d583146",
   "82_abaker" : "d583147",
   "215_grabow" : "d583148",
   "222_duvivier" : "d583149",
   "366_rberrios" : "d583150",
   "210_dxyang" : "d583100",
   "238_junkyung" : "d583101",
   "361_islas" : "d583102",
   "448" : "d583103",
   "187_jaredlee" : "d583104",
   "273_kdagon" : "d583105",
   "149_liuh" : "d583106",
   "279_schwantes" : "d583107",
   "60_pinto" : "d583108",
   "WACC_Dependence_on_Solar_Activity" : "d583109",
   "275_domingom" : "d583110",
   "445" : "d583111",
   "TIE-GCM_2017_Solar_Storm" : "d583112",
   "123_andrew" : "d583113",
   "453" : "d583114",
   "367_mclong" : "d583115",
   "258_jiangzhu" : "d583116",
   "136_hannay" : "d583117",
   "173B_dcherian" : "d583118",
   "407_islas" : "d583119",
   "189_islas" : "d583120",
   "289_shields" : "d583121",
   "415_mcinerney" : "d583122",
   "151_dll" : "d583123",
   "460" : "d583124",
   "117_phamkh" : "d583125",
   "109_erichend" : "d583126",
   "412" : "d583127",
   "390_knocasio" : "d583128",
   "382_kumar" : "d583129",
   "470" : "d583130",
   "371_abaker" : "d583131",
   "CESM-cocco_CO2_experiments" : "d583132",
   "fuel_moisture_content" : "d583133",
   "81_rberrios" : "d583134",
   "286_knocasio" : "d583135",
   "383_stebbins" : "d583136",
   "256_tilmes" : "d583137",
   '371_abaker' : 'd583131',
   # icarus
   'icarus.experiment.403' : 'd789010',
   'icarus.experiment.404' : 'd789011',
   'icarus.experiment.390' : 'd789014',
   'icarus.experiment.651' : 'd789012',
   'icarus.experiment.397' : 'd789013',
   'icarus.experiment.401' : 'd789015',
   'icarus.experiment.398' : 'd789016',
   'icarus.experiment.95' : 'd789017',
   'icarus.experiment.400' : 'd789018',
   'icarus.experiment.407' : 'd789019',
   'icarus.experiment.396' : 'd789020',
   'icarus.experiment.252' : 'd789021',
   'icarus.experiment.97' : 'd789022',
   'icarus.experiment.408' : 'd789023',
   'icarus.experiment.406' : 'd789024',
   'icarus.experiment.405' : 'd789025',
   'icarus.experiment.250' : 'd789026',
   'icarus.experiment.247' : 'd789027',
   'icarus.experiment.249' : 'd789028',
   'icarus.experiment.265' : 'd789029',
   'icarus.experiment.410' : 'd789030',
   'icarus.experiment.268' : 'd789031',
   'icarus.experiment.263' : 'd789032',
   'icarus.experiment.260' : 'd789033',
   'icarus.experiment.94' : 'd789034',
   'icarus.experiment.264' : 'd789035',
   'icarus.experiment.267' : 'd789036',
   'icarus.experiment.399' : 'd789037',
   'icarus.experiment.248' : 'd789038',
   'icarus.experiment.237' : 'd789039',
   'icarus.experiment.652' : 'd789040',
   'icarus.experiment.409' : 'd789041',
   'icarus.experiment.392' : 'd789042',
   'icarus.experiment.153' : 'd789043',
   'icarus.experiment.266' : 'd789044',
   'icarus.experiment.262' : 'd789045',
   'icarus.experiment.261' : 'd789046',
   'icarus.experiment.243' : 'd789047',
   'icarus.experiment.269' : 'd789048',
   'icarus.experiment.391' : 'd789049',
   'icarus.experiment.244' : 'd789050',
   'icarus.experiment.158' : 'd789051',
   'icarus.experiment.160' : 'd789052',
   'icarus.experiment.156' : 'd789053',
   'icarus.experiment.246' : 'd789054',
   'icarus.experiment.245' : 'd789055',
   'icarus.experiment.393' : 'd789056',
   'icarus.experiment.154' : 'd789057',
   'icarus.experiment.157' : 'd789058',
   'icarus.experiment.394' : 'd789059',
   'icarus.experiment.619' : 'd789060',
   'icarus.experiment.159' : 'd789061',
   'icarus.experiment.648' : 'd789062',
   'icarus.experiment.155' : 'd789063',
   'icarus.experiment.647' : 'd789064',
   'icarus.experiment.449' : 'd789065',
   'icarus.experiment.650' : 'd789066',
   'icarus.experiment.644' : 'd789067',
   'icarus.experiment.645' : 'd789068',
   'icarus.experiment.527' : 'd789069',
   'icarus.experiment.100' : 'd789070',
   'icarus.experiment.112' : 'd789071',
   'icarus.experiment.658' : 'd789072',
   'icarus.experiment.222' : 'd789073',
   'icarus.experiment.649' : 'd789074',
   'icarus.experiment.251' : 'd789076',
   'icarus.experiment.643' : 'd789077',
   'icarus.experiment.922' : 'd789079',
   'icarus.experiment.646' : 'd789080',
   'icarus.experiment.618' : 'd789081',
   'icarus.experiment.612' : 'd789082',
   'icarus.experiment.691' : 'd789083',
   'icarus.experiment.924' : 'd789084',
   'icarus.experiment.920' : 'd789085',
   'icarus.experiment.610' : 'd789086',
   'icarus.experiment.692' : 'd789087',
   'icarus.experiment.611' : 'd789088',
   'icarus.experiment.225' : 'd789089',
   'icarus.experiment.613' : 'd789090',
   'icarus.experiment.921' : 'd789091',
   'icarus.experiment.918' : 'd789092',
   'icarus.experiment.617' : 'd789093',
   'icarus.experiment.693' : 'd789094',
   'icarus.experiment.220' : 'd789095',
   'icarus.experiment.620' : 'd789096',
   'icarus.experiment.694' : 'd789097',
   'icarus.experiment.224' : 'd789098',
   'icarus.experiment.919' : 'd789099',
   'icarus.experiment.615' : 'd789100',
   'icarus.experiment.221' : 'd789101',
   'icarus.experiment.616' : 'd789102',
   'icarus.experiment.543' : 'd789103',
   'icarus.experiment.498' : 'd789104',
   'icarus.experiment.871' : 'd789105',
   'icarus.experiment.591' : 'd789106',
   'icarus.experiment.215' : 'd789107',
   'icarus.experiment.614' : 'd789108',
   'icarus.experiment.621' : 'd789109',
   'icarus.experiment.923' : 'd789117',
   'icarus.experiment.872' : 'd789110',
   'icarus.experiment.882' : 'd789111',
   'icarus.experiment.529' : 'd789112',
   'icarus.experiment.695' : 'd789113',
   'icarus.experiment.501' : 'd789140',
   'icarus.experiment.887' : 'd789118',
   'icarus.experiment.588' : 'd789154',
   'icarus.experiment.875' : 'd789155',
   'icarus.experiment.589' : 'd789192',
   'icarus.experiment.884' : 'd789193',
   'icarus.experiment.587' : 'd789194',
   'icarus.experiment.502' : 'd789195',
   'icarus.experiment.148' : 'd789196',
   'icarus.experiment.609' : 'd789197',
   'icarus.experiment.885' : 'd789198',
   'icarus.experiment.586' : 'd789199',
   'icarus.experiment.585' : 'd789200',
   'icarus.experiment.212' : 'd789201',
   'icarus.experiment.497' : 'd789202',
   'icarus.experiment.590' : 'd789203',
   'icarus.experiment.889' : 'd789204',
   'icarus.experiment.532' : 'd789245',
   'icarus.experiment.873' : 'd789246',
   'icarus.experiment.881' : 'd789247',
   'icarus.experiment.876' : 'd789248',
   'icarus.experiment.888' : 'd789249',
   'icarus.experiment.879' : 'd789250',
   'icarus.experiment.75' : 'd789251',
   'icarus.experiment.149' : 'd789252',
   'icarus.experiment.544' : 'd789253',
   'icarus.experiment.622' : 'd789254',
   'icarus.experiment.592' : 'd789255',
   'icarus.experiment.302' : 'd789256',
   'icarus.experiment.505' : 'd789257',
   'icarus.experiment.880' : 'd789258',
   'icarus.experiment.886' : 'd789259',
   'icarus.experiment.593' : 'd789260',
   'icarus.experiment.494' : 'd789261',
   'icarus.experiment.696' : 'd789269',
   'icarus.experiment.513' : 'd789281',
   'icarus.experiment.883' : 'd789282',
   'icarus.experiment.515' : 'd789283',
   'icarus.experiment.447' : 'd789284',
   'icarus.experiment.878' : 'd789285',
   'icarus.experiment.484' : 'd789286',
   'icarus.experiment.427' : 'd789287',
   'icarus.experiment.442' : 'd789308',
   'icarus.experiment.152' : 'd789309',
   'icarus.experiment.486' : 'd789310',
   'icarus.experiment.723' : 'd789311',
   'icarus.experiment.597' : 'd789312',
   'icarus.experiment.482' : 'd789313',
   'icarus.experiment.534' : 'd789314',
   'icarus.experiment.877' : 'd789315',
   'icarus.experiment.413' : 'd789316',
   'icarus.experiment.533' : 'd789317',
   'icarus.experiment.415' : 'd789318',
   'icarus.experiment.517' : 'd789319',
   'icarus.experiment.440' : 'd789320',
   'icarus.experiment.511' : 'd789321',
   'icarus.experiment.443' : 'd789322',
   'icarus.experiment.436' : 'd789323',
   'icarus.experiment.428' : 'd789324',
   'icarus.experiment.481' : 'd789325',
   'icarus.experiment.699' : 'd789326',
   'icarus.experiment.434' : 'd789334',
   'icarus.experiment.437' : 'd789372',
   'icarus.experiment.596' : 'd789373',
   'icarus.experiment.432' : 'd789374',
   'icarus.experiment.542' : 'd789375',
   'icarus.experiment.175' : 'd789376',
   'icarus.experiment.480' : 'd789377',
   'icarus.experiment.441' : 'd789378',
   'icarus.experiment.357' : 'd789379',
   'icarus.experiment.204' : 'd789380',
   'icarus.experiment.256' : 'd789381',
   'icarus.experiment.358' : 'd789382',
   'icarus.experiment.870' : 'd789383',
   'icarus.experiment.435' : 'd789427',
   'icarus.experiment.416' : 'd789428',
   'icarus.experiment.500' : 'd789429',
   'icarus.experiment.488' : 'd789430',
   'icarus.experiment.174' : 'd789431',
   'icarus.experiment.240' : 'd789432',
   'icarus.experiment.176' : 'd789433',
   'icarus.experiment.207' : 'd789434',
   'icarus.experiment.483' : 'd789435',
   'icarus.experiment.531' : 'd789436',
   'icarus.experiment.420' : 'd789445',
   'icarus.experiment.582' : 'd789446',
   'icarus.experiment.425' : 'd789447',
   'icarus.experiment.279' : 'd789448',
   'icarus.experiment.277' : 'd789449',
   'icarus.experiment.254' : 'd789450',
   'icarus.experiment.418' : 'd789451',
   'icarus.experiment.530' : 'd789452',
   'icarus.experiment.424' : 'd789453',
   'icarus.experiment.520' : 'd789454',
   'icarus.experiment.701' : 'd789455',
   'icarus.experiment.423' : 'd789456',
   'icarus.experiment.539' : 'd789457',
   'icarus.experiment.338' : 'd789458',
   'icarus.experiment.322' : 'd789459',
   'icarus.experiment.275' : 'd789460',
   'icarus.experiment.433' : 'd789461',
   'icarus.experiment.353' : 'd789462',
   'icarus.experiment.541' : 'd789465',
   'icarus.experiment.430' : 'd789466',
   'icarus.experiment.448' : 'd789467',
   'icarus.experiment.242' : 'd789468',
   'icarus.experiment.492' : 'd789469',
   'icarus.experiment.328' : 'd789470',
   'icarus.experiment.354' : 'd789471',
   'icarus.experiment.499' : 'd789472',
   'icarus.experiment.283' : 'd789473',
   'icarus.experiment.141' : 'd789474',
   'icarus.experiment.727' : 'd789475',
   'icarus.experiment.421' : 'd789476',
   'icarus.experiment.334' : 'd789477',
   'icarus.experiment.273' : 'd789479',
   'icarus.experiment.506' : 'd789480',
   'icarus.experiment.293' : 'd789481',
   'icarus.experiment.475' : 'd789482',
   'icarus.experiment.332' : 'd789483',
   'icarus.experiment.336' : 'd789484',
   'icarus.experiment.340' : 'd789485',
   'icarus.experiment.471' : 'd789486',
   'icarus.experiment.496' : 'd789487',
   'icarus.experiment.438' : 'd789488',
   'icarus.experiment.281' : 'd789489',
   'icarus.experiment.330' : 'd789490',
   'icarus.experiment.491' : 'd789491',
   'icarus.experiment.595' : 'd789492',
   'icarus.experiment.487' : 'd789493',
   'icarus.experiment.493' : 'd789505',
   'icarus.experiment.241' : 'd789506',
   'icarus.experiment.388' : 'd789507',
   'icarus.experiment.380' : 'd789508',
   'icarus.experiment.381' : 'd789509',
   'icarus.experiment.473' : 'd789510',
   'icarus.experiment.575' : 'd789511',
   'icarus.experiment.536' : 'd789512',
   'icarus.experiment.431' : 'd789513',
   'icarus.experiment.284' : 'd789514',
   'icarus.experiment.323' : 'd789515',
   'icarus.experiment.303' : 'd789516',
   'icarus.experiment.326' : 'd789517',
   'icarus.experiment.419' : 'd789518',
   'icarus.experiment.378' : 'd789519',
   'icarus.experiment.507' : 'd789520',
   'icarus.experiment.102' : 'd789521',
   'icarus.experiment.537' : 'd789522',
   'icarus.experiment.255' : 'd789523',
   'icarus.experiment.375' : 'd789524',
   'icarus.experiment.853' : 'd789525',
   'icarus.experiment.439' : 'd789526',
   'icarus.experiment.538' : 'd789527',
   'icarus.experiment.329' : 'd789528',
   'icarus.experiment.150' : 'd789529',
   'icarus.experiment.509' : 'd789530',
   'icarus.experiment.258' : 'd789531',
   'icarus.experiment.576' : 'd789532',
   'icarus.experiment.253' : 'd789533',
   'icarus.experiment.278' : 'd789542',
   'icarus.experiment.297' : 'd789543',
   'icarus.experiment.348' : 'd789544',
   'icarus.experiment.855' : 'd789545',
   'icarus.experiment.725' : 'd789546',
   'icarus.experiment.623' : 'd789551',
   'icarus.experiment.288' : 'd789552',
   'icarus.experiment.426' : 'd789567',
   'icarus.experiment.724' : 'd789568',
   'icarus.experiment.257' : 'd789569',
   'icarus.experiment.111' : 'd789570',
   'icarus.experiment.259' : 'd789571',
   'icarus.experiment.852' : 'd789572',
   'icarus.experiment.349' : 'd789573',
   'icarus.experiment.854' : 'd789574',
   'icarus.experiment.389' : 'd789575',
   'icarus.experiment.339' : 'd789576',
   'icarus.experiment.490' : 'd789577',
   'icarus.experiment.142' : 'd789578',
   'icarus.experiment.540' : 'd789579',
   'icarus.experiment.120' : 'd789580',
   'icarus.experiment.298' : 'd789581',
   'icarus.experiment.282' : 'd789582',
   'icarus.experiment.516' : 'd789583',
   'icarus.experiment.300' : 'd789584',
   'icarus.experiment.573' : 'd789585',
   'icarus.experiment.113' : 'd789586',
   'icarus.experiment.849' : 'd789587',
   'icarus.experiment.756' : 'd789588',
   'icarus.experiment.755' : 'd789589',
   'icarus.experiment.337' : 'd789590',
   'icarus.experiment.151' : 'd789591',
   'icarus.experiment.274' : 'd789592',
   'icarus.experiment.371' : 'd789593',
   'icarus.experiment.905' : 'd789594',
   'icarus.experiment.295' : 'd789595',
   'icarus.experiment.118' : 'd789596',
   'icarus.experiment.583' : 'd789597',
   'icarus.experiment.535' : 'd789598',
   'icarus.experiment.276' : 'd789599',
   'icarus.experiment.335' : 'd789600',
   'icarus.experiment.292' : 'd789601',
   'icarus.experiment.122' : 'd789602',
   'icarus.experiment.296' : 'd789603',
   'icarus.experiment.414' : 'd789604',
   'icarus.experiment.333' : 'd789605',
   'icarus.experiment.577' : 'd789606',
   'icarus.experiment.512' : 'd789607',
   'icarus.experiment.472' : 'd789608',
   'icarus.experiment.376' : 'd789609',
   'icarus.experiment.857' : 'd789610',
   'icarus.experiment.299' : 'd789611',
   'icarus.experiment.104' : 'd789612',
   'icarus.experiment.514' : 'd789613',
   'icarus.experiment.280' : 'd789614',
   'icarus.experiment.79' : 'd789615',
   'icarus.experiment.341' : 'd789616',
   'icarus.experiment.271' : 'd789617',
   'icarus.experiment.121' : 'd789618',
   'icarus.experiment.386' : 'd789619',
   'icarus.experiment.697' : 'd789620',
   'icarus.experiment.485' : 'd789621',
   'icarus.experiment.607' : 'd789622',
   'icarus.experiment.594' : 'd789623',
   'icarus.experiment.574' : 'd789624',
   'icarus.experiment.291' : 'd789625',
   'icarus.experiment.331' : 'd789626',
   'icarus.experiment.369' : 'd789627',
   'icarus.experiment.287' : 'd789628',
   'icarus.experiment.384' : 'd789629',
   'icarus.experiment.851' : 'd789630',
   'icarus.experiment.355' : 'd789631',
   'icarus.experiment.117' : 'd789632',
   'icarus.experiment.201' : 'd789633',
   'icarus.experiment.850' : 'd789634',
   'icarus.experiment.301' : 'd789635',
   'icarus.experiment.370' : 'd789636',
   'icarus.experiment.856' : 'd789637',
   'icarus.experiment.385' : 'd789638',
   'icarus.experiment.726' : 'd789639',
   'icarus.experiment.858' : 'd789640',
   'icarus.experiment.114' : 'd789641',
   'icarus.experiment.578' : 'd789642',
   'icarus.experiment.387' : 'd789643',
   'icarus.experiment.508' : 'd789644',
   'icarus.experiment.860' : 'd789645',
   'icarus.experiment.859' : 'd789646',
   'icarus.experiment.290' : 'd789647',
   'icarus.experiment.545' : 'd789648',
   'icarus.experiment.519' : 'd789649',
   'icarus.experiment.289' : 'd789650',
   'icarus.experiment.568' : 'd789651',
   'icarus.experiment.356' : 'd789652',
   'icarus.experiment.372' : 'd789653',
   'icarus.experiment.603' : 'd789654',
   'icarus.experiment.272' : 'd789655',
   'icarus.experiment.579' : 'd789656',
   'icarus.experiment.286' : 'd789657',
   'icarus.experiment.580' : 'd789658',
   'icarus.experiment.203' : 'd789659',
   'icarus.experiment.546' : 'd789660',
   'icarus.experiment.624' : 'd789661',
   'icarus.experiment.489' : 'd789662',
   'icarus.experiment.119' : 'd789663',
   'icarus.experiment.383' : 'd789664',
   'icarus.experiment.703' : 'd789665',
   'icarus.experiment.640' : 'd789566',
   'icarus.experiment.294' : 'd789565',
   'icarus.experiment.567' : 'd789564',
   'icarus.experiment.629' : 'd789563',
   'icarus.experiment.564' : 'd789562',
   'icarus.experiment.638' : 'd789561',
   'icarus.experiment.637' : 'd789560',
   'icarus.experiment.633' : 'd789559',
   'icarus.experiment.625' : 'd789558',
   'icarus.experiment.495' : 'd789557',
   'icarus.experiment.635' : 'd789556',
   'icarus.experiment.604' : 'd789555',
   'icarus.experiment.605' : 'd789554',
   'icarus.experiment.598' : 'd789553',
   'icarus.experiment.116' : 'd789550',
   'icarus.experiment.457' : 'd789549',
   'icarus.experiment.606' : 'd789548',
   'icarus.experiment.566' : 'd789547',
   'icarus.experiment.608' : 'd789541',
   'icarus.experiment.469' : 'd789540',
   'icarus.experiment.599' : 'd789539',
   'icarus.experiment.864' : 'd789538',
   'icarus.experiment.861' : 'd789537',
   'icarus.experiment.866' : 'd789536',
   'icarus.experiment.601' : 'd789535',
   'icarus.experiment.565' : 'd789534',
   'icarus.experiment.627' : 'd789504',
   'icarus.experiment.862' : 'd789503',
   'icarus.experiment.458' : 'd789502',
   'icarus.experiment.639' : 'd789501',
   'icarus.experiment.865' : 'd789500',
   'icarus.experiment.602' : 'd789499',
   'icarus.experiment.867' : 'd789498',
   'icarus.experiment.327' : 'd789497',
   'icarus.experiment.863' : 'd789496',
   'icarus.experiment.868' : 'd789495',
   'icarus.experiment.757' : 'd789494',
   'icarus.experiment.759' : 'd789478',
   'icarus.experiment.760' : 'd789464',
   'icarus.experiment.937' : 'd789463',
   'icarus.experiment.476' : 'd789444',
   'icarus.experiment.477' : 'd789443',
   'icarus.experiment.761' : 'd789442',
   'icarus.experiment.106' : 'd789441',
   'icarus.experiment.115' : 'd789440',
   'icarus.experiment.874' : 'd789439',
   'icarus.experiment.935' : 'd789438',
   'icarus.experiment.930' : 'd789437',
   'icarus.experiment.474' : 'd789426',
   'icarus.experiment.933' : 'd789425',
   'icarus.experiment.766' : 'd789424',
   'icarus.experiment.758' : 'd789423',
   'icarus.experiment.932' : 'd789422',
   'icarus.experiment.934' : 'd789421',
   'icarus.experiment.936' : 'd789420',
   'icarus.experiment.929' : 'd789419',
   'icarus.experiment.824' : 'd789418',
   'icarus.experiment.478' : 'd789417',
   'icarus.experiment.359' : 'd789416',
   'icarus.experiment.325' : 'd789415',
   'icarus.experiment.938' : 'd789414',
   'icarus.experiment.931' : 'd789413',
   'icarus.experiment.928' : 'd789412',
   'icarus.experiment.470' : 'd789411',
   'icarus.experiment.145' : 'd789410',
   'icarus.experiment.767' : 'd789409',
   'icarus.experiment.360' : 'd789408',
   'icarus.experiment.351' : 'd789407',
   'icarus.experiment.352' : 'd789406',
   'icarus.experiment.362' : 'd789405',
   'icarus.experiment.780' : 'd789404',
   'icarus.experiment.772' : 'd789403',
   'icarus.experiment.361' : 'd789402',
   'icarus.experiment.781' : 'd789401',
   'icarus.experiment.777' : 'd789400',
   'icarus.experiment.830' : 'd789399',
   'icarus.experiment.778' : 'd789398',
   'icarus.experiment.765' : 'd789397',
   'icarus.experiment.779' : 'd789396',
   'icarus.experiment.776' : 'd789395',
   'icarus.experiment.826' : 'd789394',
   'icarus.experiment.762' : 'd789393',
   'icarus.experiment.827' : 'd789392',
   'icarus.experiment.764' : 'd789391',
   'icarus.experiment.831' : 'd789390',
   'icarus.experiment.510' : 'd789389',
   'icarus.experiment.786' : 'd789388',
   'icarus.experiment.828' : 'd789387',
   'icarus.experiment.792' : 'd789386',
   'icarus.experiment.373' : 'd789385',
   'icarus.experiment.829' : 'd789384',
   'icarus.experiment.869' : 'd789371',
   'icarus.experiment.811' : 'd789370',
   'icarus.experiment.81' : 'd789369',
   'icarus.experiment.784' : 'd789368',
   'icarus.experiment.785' : 'd789367',
   'icarus.experiment.787' : 'd789366',
   'icarus.experiment.794' : 'd789365',
   'icarus.experiment.763' : 'd789364',
   'icarus.experiment.791' : 'd789363',
   'icarus.experiment.518' : 'd789362',
   'icarus.experiment.771' : 'd789361',
   'icarus.experiment.805' : 'd789360',
   'icarus.experiment.808' : 'd789359',
   'icarus.experiment.796' : 'd789358',
   'icarus.experiment.795' : 'd789357',
   'icarus.experiment.806' : 'd789356',
   'icarus.experiment.783' : 'd789355',
   'icarus.experiment.812' : 'd789354',
   'icarus.experiment.809' : 'd789353',
   'icarus.experiment.810' : 'd789352',
   'icarus.experiment.82' : 'd789351',
   'icarus.experiment.793' : 'd789350',
   'icarus.experiment.790' : 'd789349',
   'icarus.experiment.807' : 'd789348',
   'icarus.experiment.789' : 'd789347',
   'icarus.experiment.798' : 'd789346',
   'icarus.experiment.800' : 'd789345',
   'icarus.experiment.799' : 'd789344',
   'icarus.experiment.788' : 'd789343',
   'icarus.experiment.797' : 'd789342',
   'icarus.experiment.782' : 'd789340',
   'icarus.experiment.374' : 'd789339',
   'icarus.experiment.801' : 'd789338',
   'icarus.experiment.804' : 'd789337',
   'icarus.experiment.802' : 'd789336',
   'icarus.experiment.803' : 'd789335',
   'icarus.experiment.743' : 'd789333',
   'icarus.experiment.744' : 'd789332',
   'icarus.experiment.735' : 'd789331',
   'icarus.experiment.737' : 'd789330',
   'icarus.experiment.736' : 'd789329',
   'icarus.experiment.745' : 'd789328',
   'icarus.experiment.746' : 'd789327',
   'icarus.experiment.738' : 'd789307',
   'icarus.experiment.749' : 'd789306',
   'icarus.experiment.734' : 'd789305',
   'icarus.experiment.666' : 'd789304',
   'icarus.experiment.739' : 'd789303',
   'icarus.experiment.663' : 'd789302',
   'icarus.experiment.681' : 'd789301',
   'icarus.experiment.690' : 'd789300',
   'icarus.experiment.688' : 'd789299',
   'icarus.experiment.747' : 'd789298',
   'icarus.experiment.689' : 'd789297',
   'icarus.experiment.684' : 'd789296',
   'icarus.experiment.683' : 'd789295',
   'icarus.experiment.679' : 'd789294',
   'icarus.experiment.682' : 'd789293',
   'icarus.experiment.685' : 'd789292',
   'icarus.experiment.680' : 'd789291',
   'icarus.experiment.678' : 'd789290',
   'icarus.experiment.667' : 'd789289',
   'icarus.experiment.674' : 'd789288',
   'icarus.experiment.665' : 'd789280',
   'icarus.experiment.672' : 'd789279',
   'icarus.experiment.664' : 'd789278',
   'icarus.experiment.676' : 'd789277',
   'icarus.experiment.675' : 'd789276',
   'icarus.experiment.671' : 'd789275',
   'icarus.experiment.673' : 'd789274',
   'icarus.experiment.748' : 'd789273',
   'icarus.experiment.742' : 'd789272',
   'icarus.experiment.750' : 'd789271',
   'icarus.experiment.668' : 'd789270',
   'icarus.experiment.662' : 'd789268',
   'icarus.experiment.661' : 'd798267',
   'icarus.experiment.660' : 'd789266',
   'icarus.experiment.659' : 'd789265',
   'icarus.experiment.669' : 'd789264',
   'icarus.experiment.740' : 'd789263',
   'icarus.experiment.741' : 'd789262',
   'icarus.experiment.162' : 'd789244',
   'icarus.experiment.687' : 'd789243',
   'icarus.experiment.144' : 'd789242',
   'icarus.experiment.837' : 'd789241',
   'icarus.experiment.836' : 'd789240',
   'icarus.experiment.835' : 'd789239',
   'icarus.experiment.834' : 'd789238',
   'icarus.experiment.833' : 'd789237',
   'icarus.experiment.845' : 'd789236',
   'icarus.experiment.844' : 'd789235',
   'icarus.experiment.841' : 'd789234',
   'icarus.experiment.842' : 'd789233',
   'icarus.experiment.847' : 'd789232',
   'icarus.experiment.843' : 'd789231',
   'icarus.experiment.840' : 'd789230',
   'icarus.experiment.848' : 'd789229',
   'icarus.experiment.832' : 'd789228',
   'icarus.experiment.846' : 'd789227',
   'icarus.experiment.838' : 'd789226',
   'icarus.experiment.839' : 'd789225',
   'icarus.experiment.907' : 'd789224',
   'icarus.experiment.754' : 'd789223',
   'icarus.experiment.773' : 'd789222',
   'icarus.experiment.306' : 'd789221',
   'icarus.experiment.310' : 'd789220',
   'icarus.experiment.305' : 'd789219',
   'icarus.experiment.813' : 'd789218',
   'icarus.experiment.304' : 'd789217',
   'icarus.experiment.814' : 'd789216',
   'icarus.experiment.308' : 'd789215',
   'icarus.experiment.459' : 'd789214',
   'icarus.experiment.311' : 'd789213',
   'icarus.experiment.468' : 'd789212',
   'icarus.experiment.463' : 'd789211',
   'icarus.experiment.460' : 'd789210',
   'icarus.experiment.465' : 'd789209',
   'icarus.experiment.462' : 'd789208',
   'icarus.experiment.467' : 'd789207',
   'icarus.experiment.464' : 'd789206',
   'icarus.experiment.466' : 'd789205',
   'icarus.experiment.227' : 'd789191',
   'icarus.experiment.318' : 'd789190',
   'icarus.experiment.231' : 'd789189',
   'icarus.experiment.312' : 'd789188',
   'icarus.experiment.307' : 'd789187',
   'icarus.experiment.229' : 'd789186',
   'icarus.experiment.230' : 'd789185',
   'icarus.experiment.309' : 'd789184',
   'icarus.experiment.316' : 'd789183',
   'icarus.experiment.315' : 'd789182',
   'icarus.experiment.382' : 'd789181',
   'icarus.experiment.167' : 'd789180',
   'icarus.experiment.168' : 'd789179',
   'icarus.experiment.317' : 'd789178',
   'icarus.experiment.379' : 'd789177',
   'icarus.experiment.314' : 'd789176',
   'icarus.experiment.164' : 'd789175',
   'icarus.experiment.163' : 'd789174',
   'icarus.experiment.165' : 'd789173',
   'icarus.experiment.143' : 'd789172',
   'icarus.experiment.321' : 'd789171',
   'icarus.experiment.166' : 'd789170',
   'icarus.experiment.319' : 'd789169',
   'icarus.experiment.161' : 'd789168',
   'icarus.experiment.313' : 'd789167',
   'icarus.experiment.147' : 'd789166',
   'icarus.experiment.218' : 'd789165',
   'icarus.experiment.217' : 'd789164',
   'icarus.experiment.216' : 'd789163',
   'icarus.experiment.213' : 'd789162',
   'icarus.experiment.214' : 'd789161',
   'icarus.experiment.320' : 'd789160',
   'icarus.experiment.226' : 'd789159',
   'icarus.experiment.109' : 'd789158',
   'icarus.experiment.228' : 'd789157',
   'icarus.experiment.108' : 'd789156',
   'icarus.experiment.180' : 'd789153',
   'icarus.experiment.77' : 'd789152',
   'icarus.experiment.211' : 'd789151',
   'icarus.experiment.187' : 'd789150',
   'icarus.experiment.188' : 'd789149',
   'icarus.experiment.185' : 'd789148',
   'icarus.experiment.205' : 'd789147',
   'icarus.experiment.189' : 'd789146',
   'icarus.experiment.209' : 'd789145',
   'icarus.experiment.186' : 'd789144',
   'icarus.experiment.210' : 'd789143',
   'icarus.experiment.206' : 'd789142',
   'icarus.experiment.208' : 'd789141',
   'icarus.experiment.177' : 'd789136',
   'icarus.experiment.182' : 'd789133',
   'icarus.experiment.184' : 'd789132',
   'icarus.experiment.178' : 'd789131',
   'icarus.experiment.183' : 'd789130',
   'icarus.experiment.179' : 'd789129',
   'icarus.experiment.196' : 'd789128',
   'icarus.experiment.190' : 'd789127',
   'icarus.experiment.181' : 'd789126',
   'icarus.experiment.192' : 'd789125',
   'icarus.experiment.193' : 'd789124',
   'icarus.experiment.195' : 'd789123',
   'icarus.experiment.200' : 'd789122',
   'icarus.experiment.199' : 'd789121',
   'icarus.experiment.191' : 'd789120',
   'icarus.experiment.194' : 'd789119',
   'icarus.experiment.198' : 'd789116',
   'icarus.experiment.107' : 'd789115',
   'icarus.experiment.197' : 'd789114'
}

ALLIDS = list(DSIDS.keys())

WFILES = {}

#
# main function to run this program
#
def main():

   params = {}  # array of input values
   argv = sys.argv[1:]
   opt = None
   
   for arg in argv:
      if arg == "-b":
         PgLOG.PGLOG['BCKGRND'] = 1
      elif re.match(r'^-[msNy]$', arg):
         opt = arg[1]
         params[opt] = []
      elif re.match(r'^-', arg):
         PgLOG.pglog(arg + ": Invalid Option", PgLOG.LGWNEX)
      elif opt:
         params[opt].append(arg)
      else:
         PgLOG.pglog(arg + ": Value passed in without leading option", PgLOG.LGWNEX)

   if not opt:
      PgLOG.show_usage('fillgdexusage')
   elif 's' not in params:
      PgLOG.pglog("-s: Missing dataset short name to gather GDEX metrics", PgLOG.LGWNEX)
   elif len(params) < 2:
      PgLOG.pglog("-(m|N|y): Missing Month, NumberDays or Year to gather GDEX metrics", PgLOG.LGWNEX)
      
   
   PgLOG.cmdlog("fillgdexusage {}".format(' '.join(argv)))
   dranges = get_date_ranges(params)
   dsids = get_dataset_ids(params['s'])
   if dranges and dsids: fill_gdex_usages(dsids, dranges)
   PgLOG.pglog(None, PgLOG.LOGWRN|PgLOG.SNDEML)  # send email out if any

   sys.exit(0)

#
# connect to the gdex database esg-production
#
def gdex_dbname():
   PgDBI.set_scname('gdex-production', 'metrics', 'gateway-reader', None, 'sagedbprodalma.ucar.edu')

#
# get datasets
#
def get_dataset_ids(dsnames):

   gdex_dbname()
   dsids = []
   tbname = 'metadata.dataset'
   for dsname in dsnames:
      if re.match(r'^all$', dsname, re.I): return get_dataset_ids(ALLIDS)
      if dsname not in DSIDS:
         PgLOG.pglog(dsname + ": Unknown GDEX dataset short name", PgLOG.LOGWRN)
         continue
      bt = tm()
      pgrec = PgDBI.pgget(tbname, 'id', "short_name = '{}'".format(dsname))
      if not (pgrec and pgrec['id']): continue
      rdaid = DSIDS[dsname]
      strids = "{}-{}".format(dsname, rdaid)
      gdexid = pgrec['id']
      gdexids = [gdexid]
      ccnt = 1
      ccnt += recursive_dataset_ids(gdexid, gdexids)
      dsids.append([dsname, rdaid, gdexids, strids])
      rmsg = PgLOG.seconds_to_string_time(tm() - bt)
      PgLOG.pglog("{}: Found {} GDEX dsid/subdsids in {} at {}".format(strids, ccnt, rmsg, PgLOG.current_datetime()), PgLOG.LOGWRN)

   if not dsids: PgLOG.pglog("No Dataset Id identified to gather GDEX metrics", PgLOG.LOGWRN)

   return dsids

#
# get gdexids recursivley
#
def recursive_dataset_ids(pgdexid, gdexids):

   tbname = 'metadata.dataset'
   pgrecs = PgDBI.pgmget(tbname, 'id', "parent_dataset_id = '{}'".format(pgdexid))
   if not pgrecs: return 0

   ccnt = 0
   for gdexid in pgrecs['id']:
      if gdexid in gdexids: continue
      gdexids.append(gdexid)
      ccnt += 1
      ccnt += recursive_dataset_ids(gdexid, gdexids)

   return ccnt

#
# get the date ranges for given condition
#
def get_date_ranges(inputs):

   dranges = []
   for opt in inputs:
      for input in inputs[opt]:
         # get date range
         dates = []
         if opt == 'N':
            dates.append(PgUtil.adddate(USAGE['CDATE'], 0, 0, -int(input)))
            dates.append(USAGE['CDATE'])
         elif opt == 'm':
            tms = input.split('-')
            dates.append(PgUtil.fmtdate(int(tms[0]), int(tms[1]), 1))
            dates.append(PgUtil.enddate(dates[0], 0, 'M'))
         elif opt == 'y':
            dates.append(input + "-01-01")
            dates.append(input + "-12-31")
         if dates: dranges.append(dates)

   return dranges

#
# get file download records for given dsid
#
def get_dsid_records(gdexids, dates, strids):

   gdex_dbname()
   tbname = 'metrics.file_download'
   fields = ('date_completed, remote_address, logical_file_size, logical_file_name, user_agent_name, bytes_sent, '
             'subset_file_size, range_request, dataset_file_size, dataset_file_name')
   dscnt = len(gdexids)
   dscnd = "dataset_id "
   if dscnt == 1:
      dscnd += "= '{}'".format(gdexids[0])
   else:
      dscnd += "IN ('" + "','".join(gdexids) + "')"
   dtcnd = "date_completed BETWEEN '{} 00:00:00' AND '{} 23:59:59'".format(dates[0], dates[1])
   cond = "{} AND {} ORDER BY date_completed".format(dscnd, dtcnd)
   PgLOG.pglog("{}: Query for {} GDEX dsid/subdsids between {} and {} at {}".format(strids, dscnt, dates[0], dates[1], PgLOG.current_datetime()), PgLOG.LOGWRN)
   pgrecs = PgDBI.pgmget(tbname, fields, cond)
   PgDBI.dssdb_dbname()

   return pgrecs

#
# Fill TDS usages into table dssdb.tdsusage from gdex access records
#
def fill_gdex_usages(dsids, dranges):

   allcnt = awcnt = lcnt = 0
   for dates in dranges:
      for dsid in dsids:
         lcnt += 1
         dsname = dsid[0]
         rdaid = dsid[1]
         gdexids = dsid[2]
         strids = dsid[3]
         bt = tm()
         pgrecs = get_dsid_records(gdexids, dates, strids)
         pgcnt = len(pgrecs['dataset_file_name']) if pgrecs else 0
         if pgcnt == 0:
            PgLOG.pglog("{}: No record found to gather GDEX usage between {} and {}".format(strids, dates[0], dates[1]), PgLOG.LOGWRN)
            continue
         rmsg = PgLOG.seconds_to_string_time(tm() - bt)
         PgLOG.pglog("{}: Got {} records in {} for processing GDEX usage at {}".format(strids, pgcnt, rmsg, PgLOG.current_datetime()), PgLOG.LOGWRN)
         wcnt = 0
         pwkey = wrec = cdate = None
         bt = tm()
         for i in range(pgcnt):
            if (i+1)%20000 == 0:
               PgLOG.pglog("{}/{} GDEX/WEB records processed to add".format(i, wcnt), PgLOG.WARNLG)

            pgrec = PgUtil.onerecord(pgrecs, i)
            dsize = pgrec['bytes_sent']
            if not dsize: continue
            (year, quarter, date, time) = get_record_date_time(pgrec['date_completed'])
            ip = pgrec['remote_address']
            engine = pgrec['user_agent_name']
            wfile = pgrec['dataset_file_name']
            if not wfile: wfile = pgrec['logic_file_name']
            wfrec = get_wfile_record(rdaid, wfile)
            if not wfrec: continue
            dsid = wfrec['dsid']
            fsize = pgrec['dataset_file_size']
            if not fsize: fsize = pgrec['logic_file_size']
            method = 'GDEX'
            if pgrec['subset_file_size'] or pgrec['range_request'] or dsize < fsize:
               wkey = "{}:{}:{}".format(ip, dsid, wfile)
            else:
               wkey = None
   
            if wrec:
               if wkey == pwkey:
                  wrec['size'] += dsize
                  continue
               wcnt += add_webfile_usage(year, wrec)
            wrec = {'ip' : ip, 'dsid' : dsid, 'wid' : wfrec['wid'], 'date' : date,
                    'time' : time, 'quarter' : quarter, 'size' : dsize,
                    'locflag' : 'C', 'method' : method}
            pwkey = wkey
            if not pwkey:
               wcnt += add_webfile_usage(year, wrec)
               wrec = None

         if wrec: wcnt += add_webfile_usage(year, wrec)
         awcnt += wcnt
         allcnt += pgcnt
         rmsg = PgLOG.seconds_to_string_time(tm() - bt)
         PgLOG.pglog("{}: {} WEB usage records added for {} GDEX entries in {}".format(strids, awcnt, allcnt, rmsg), PgLOG.LOGWRN)

def get_record_date_time(ctime):

   ms = re.search(r'^(\d+)-(\d+)-(\d+) (\d\d:\d\d:\d\d)', str(ctime))
   if ms:
      y = ms.group(1)
      m = int(ms.group(2))
      d = ms.group(3)
      q = 1 + int((m-1)/3)
      t = ms.group(4)
      return (y, q, "{}-{:02}-{}".format(y, m, d), t)
   else:
      PgLOG.pglog(str(ctime) + ": Invalid time format", PgLOG.LGEREX)

#
# Fill usage of a single online data file into table dssdb.wusage of DSS PgSQL database
#
def add_webfile_usage(year, logrec):

   table = "{}_{}".format(USAGE['WEBTBL'], year)
   cdate = logrec['date']
   ip = logrec['ip']
   cond = "wid = {} AND method = '{}' AND date_read = '{}' AND time_read = '{}'".format(logrec['wid'], logrec['method'], cdate, logrec['time'])
   if PgDBI.pgget(table, "", cond, PgLOG.LOGWRN): return 0

   wurec =  PgIPInfo.get_wuser_record(ip, cdate)
   if not wurec: return 0

   record = {'wid' : logrec['wid'], 'dsid' : logrec['dsid']}
   record['wuid_read'] = wurec['wuid']
   record['date_read'] = cdate
   record['time_read'] = logrec['time']
   record['size_read'] = logrec['size']
   record['method'] = logrec['method']
   record['locflag'] = logrec['locflag']
   record['ip'] = ip
   record['quarter'] = logrec['quarter']

   if add_web_allusage(year, logrec, wurec):
      return PgDBI.add_yearly_wusage(year, record)
   else:
      return 0

def add_web_allusage(year, logrec, wurec):

   pgrec = {'source' : 'G'}
   pgrec['email'] = wurec['email']
   pgrec['org_type'] = wurec['org_type']
   pgrec['country'] = wurec['country']
   pgrec['region'] = wurec['region']
   pgrec['dsid'] = logrec['dsid']
   pgrec['date'] = logrec['date']
   pgrec['quarter'] = logrec['quarter']
   pgrec['time'] = logrec['time']
   pgrec['size'] = logrec['size']
   pgrec['method'] = logrec['method']
   pgrec['ip'] = logrec['ip']
   return PgDBI.add_yearly_allusage(year, pgrec)

#
# return wfile.wid upon success, 0 otherwise
#
def get_wfile_record(dsid, wfile):

   wkey = "{}{}".format(dsid, wfile)
   if wkey in WFILES: return WFILES[wkey]
   wfcond = "wfile LIKE '%{}'".format(wfile)
   pgrec = None
   pgrec = PgSplit.pgget_wfile(dsid, "wid", wfcond)
   if pgrec:
      pgrec['dsid'] = dsid
      wkey = "{}{}".format(dsid, wfile)
      WFILES[wkey] = pgrec
      return pgrec

   pgrec = PgDBI.pgget("wfile_delete", "wid, dsid", "{} AND dsid = '{}'".format(wfcond, dsid))
   if not pgrec:
      mvrec = PgDBI.pgget("wmove", "wid, dsid", wfcond)
      if mvrec:
         pgrec = PgSplit.pgget_wfile(mvrec['dsid'], "wid", "wid = {}".format(pgrec['wid']))
         if pgrec: pgrec['dsid'] = mvrec['dsid']

   WFILES[wkey] = pgrec
   return pgrec

#
# call main() to start program
#
if __name__ == "__main__": main()
