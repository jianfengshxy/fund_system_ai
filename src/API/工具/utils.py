# curl --request POST \
#   --url https://fundcomapi.tiantianfunds.com/mm/FundFavor/FundFavorInfo \
#   --header 'Accept: */*' \
#   --header 'Accept-Encoding: gzip, deflate, br' \
#   --header 'Connection: keep-alive' \
#   --header 'Host: fundcomapi.tiantianfunds.com' \
#   --header 'Referer: https://mpservice.com/770ddc37537896dae8ecd8160cb25336/release/pages/fundList/all-list/index?groupId=all&groupName=全部' \
#   --header 'User-Agent: okhttp/3.12.13' \
#   --header 'clientInfo: ttjj-ZTE 7534N-Android-11' \
#   --header 'forceLog: 1' \
#   --header 'gtoken: ceaf-4a997831b1b3b90849f585f98ca6f30e' \
#   --header 'mp_instance_id: 32' \
#   --header 'traceparent: 00-0000000046aa4cae00000196718a8166-0000000000000000-01' \
#   --header 'tracestate: pid=0x6f96620,taskid=0xabc5123' \
#   --header 'validmark: Li4RtWc+9LvmhgcBNN3qg3dzZjFUt4WiApOOGmkaVZL5BWm0DcGX9NZYIxjsAsZdVcHJ8J2NdZhXTNMQR9BMpxG3EMlqXyJoFeiMLZWZZtJ1DXqiIOSu/kLYsAt37vKDFhzWESfp9O5+28eHlMZFdAOKtOr630iFFehhF8ZZ2O0=' \
#   --data 'FIELDS=MAXSG,FCODE,SHORTNAME,PDATE,NAV,ACCNAV,NAVCHGRT,NAVCHGRT100,GSZ,GSZZL,GZTIME,NEWPRICE,CHANGERATIO,ZJL,HQDATE,ISREDBAGS,SYL_Z,SYL_Y,SYL_3Y,SYL_6Y,SYL_JN,SYL_1N,SYL_2N,SYL_3N,SYL_5N,SYL_LN,RSBTYPE,RSFUNDTYPE,INDEXCODE,NEWINDEXTEXCH,TRKERROR1,ISBUY' \
#   --data product=EFund \
#   --data 'APPID=FAVOR,FAVOR_ED,FAVOR_GS' \
#   --data pageSize=176 \
#   --data passportctoken=CR0PL-qa8w6SmCGBL4KzSXeTioFwoR7HN_JmcR_yMVCGSVFCGYTR4KBYc8gQI5rUPIp-fs6Hg5yN6jIPAYli_sE4Fnm-S2TN298wRuSBAxzWaDoRd82XYXt7FuPkh57WzKu7ejHQrhMXwp-uR5zuPnQi2L1joI7KuE0jnW4Yl2E \
#   --data SortColumn= \
#   --data passportutoken=QjaJ8B6U43EzrU9QuBKxUcLl7plJD3DQnGBVESjw_tEyqhKYNefuSoxE23M_B7Jf3J0QXt9K8L11-c8kM0US8Dh8-cOaAbUY9-Grz_lOD6YHTQVF-VrpwJ3rltTFJyrpYlAiTIjmOCCKRTAZHnZpLu0sRlqnHr8eQboojFxiYI6iO6kzsJMrP02LvOzw4P_nGXUk8trx06j9Y2RFXx950V04nn1NMRjyTSRUNbPKmwTYeaI1PGmptAYRY16wQzraxG8vMqmV8HoG5zVi9ovBuh0H3rBpfAMvAPsQpNSkMYs83gdJjuXZi4pY133FWRGdIG-1Hula3rHsjdvZm56ZkLT4UjljRP3aoFZ7N_zbM-g \
#   --data 'deviceid=15a16f86a738f59811cbd40da4da1d97||iemi_tluafed_me' \
#   --data userid=cd0b7906b53b43ffa508a99744b4055b \
#   --data version=6.7.1 \
#   --data ctoken=xR1h5WuKZqVp9l_uzA4vmt1TbZvcuH97mfnMo8i25njxNggTR1F5Vy0FcmNOr7lcAhJSPqY1erg_deGhXFZ55j_xbVJbd19AHy1jCksXg7PjZtPuCTAF9keQTT-5TbG4qhOM6YtifyX15WE7Dn-F40DXYm8s_vSUBewq1S4OlzwT4k3mTLaIC4fUIttpmCxjUWgWeHBzBKLOkrYF1bvmidcxfd9G6pCYskXwInJcWiUqGVfJjWkRd1FXly1YR8og.5 \
#   --data uid=cd0b7906b53b43ffa508a99744b4055b \
#   --data CODES=020256 \
#   --data pageIndex=1 \
#   --data utoken=CTZAr6Vx9U6SCvZEIZ5zmTvaG8t53DNGjfLyDr-paGMyqI-sh4QTKVawSW82SgLIU1eNn25zIksAj3J82S29TNDksOhD93p2HYuiCWB4IL_9H2J4kelucqM__eoWiXjeCCvzTvVdQGjG6c4UCVseea4jLsXm2ANQf30bIdlb1P8.5 \
#   --data Sort= \
#   --data plat=Android \
#   --data passportid=8461315737102942

#   {
# 	"data": [
# 		{
# 			"NAV": 1.3188,
# 			"NAVCHGRT": 2.89,
# 			"CHANGERATIO": null,
# 			"MAXSG": 100000000000,
# 			"GZTIME": "2025-04-30 15:00",
# 			"NEWPRICE": null,
# 			"HQDATE": null,
# 			"FCODE": "020256",
# 			"SYL_JN": 10.38,
# 			"SYL_3Y": 5.02,
# 			"SYL_LN": 31.88,
# 			"ISBUY": "1",
# 			"SYL_3N": null,
# 			"SYL_1N": 20.3,
# 			"ZJL": null,
# 			"SYL_5N": null,
# 			"NEWINDEXTEXCH": "2",
# 			"INDEXCODE": "H30590",
# 			"NAVCHGRT100": 2.89,
# 			"SHORTNAME": "中欧中证机器人指数发起C",
# 			"TRKERROR1": 3.0957,
# 			"LABELINFO": null,
# 			"ISREDBAGS": null,
# 			"GSZ": 1.319,
# 			"GSZZL": 2.91,
# 			"SYL_6Y": 19.42,
# 			"RSBTYPE": "000001",
# 			"ACCNAV": 1.3188,
# 			"PDATE": "2025-04-30",
# 			"SYL_2N": null,
# 			"RSFUNDTYPE": "000",
# 			"SYL_Z": 2.37,
# 			"SYL_Y": -4.66
# 		}
# 	],
# 	"errorCode": 0,
# 	"firstError": null,
# 	"success": true,
# 	"hasWrongToken": null,
# 	"totalCount": 1,
# 	"expansion": {
# 		"GZTIME": "2025-04-30",
# 		"FSRQ": "2025-04-30"
# 	},
# 	"jf": "ali"
# }