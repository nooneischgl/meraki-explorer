import sys
import logging
from logging.handlers import RotatingFileHandler
from fastapi import Body, FastAPI, File
from fastapi.middleware.cors import CORSMiddleware
import os
import json
from typing import Optional
from pydantic import BaseModel
from pathlib import Path
import meraki
import io
from datetime import datetime
import motor.motor_asyncio
from bson import json_util
import time
from dotenv import load_dotenv
import random
import string
from production_config import settings as prod_settings
from development_config import settings as dev_settings
from rlog import RedisHandler

load_dotenv(verbose=True)
app = FastAPI(debug=True)
now = datetime.now()


FASTAPI_ENV_DEFAULT = 'production'
try:
    if os.getenv('FASTAPI_ENV',    FASTAPI_ENV_DEFAULT) == 'development':
        # Using a developmet configuration
        print("Environment is development")
        mongodb_url = dev_settings.mongodb_url
        mongodb_hostname = dev_settings.mongodb_hostname
        redis_hostname = dev_settings.redis_hostname
    else:
        # Using a production configuration
        print("Environment is production")
        mongodb_url = prod_settings.mongodb_url
        mongodb_hostname = prod_settings.mongodb_hostname
        redis_hostname = prod_settings.redis_hostname

except Exception as error:
    print('error: ', error)
    pass



# Creating and Configuring Logger
################################################
################################################

#Basic Logger
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s %(name)12s: %(levelname)8s > %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)

logger = logging.getLogger()
logger.addHandler(RedisHandler(channel='live_log',host=redis_hostname, port=6379))
logging.getLogger('websockets.server').setLevel(logging.ERROR)
logging.getLogger('websockets.protocol').setLevel(logging.ERROR)

#File Logger
logfile_handler = RotatingFileHandler("../log/log.txt", mode='a', maxBytes=5*1024*1024,
                                 backupCount=3, encoding=None, delay=0)
logfile_formatter = logging.Formatter('%(asctime)s %(name)12s: %(levelname)8s > %(message)s',datefmt='%Y-%m-%d %H:%M:%S')
logfile_handler.setFormatter(logfile_formatter)
logfile_handler.setLevel(logging.DEBUG)
logger.addHandler(logfile_handler)


################################################
################################################




origins = [
    "http://localhost:3000",
    "localhost:3000",
    "http://127.0.0.1:3000",
    "127.0.0.1:3000",
    "http://localhost",
    "http://127.0.0.1"
]


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)


# Initializing MONGODB DataBase
try:
    MONGO_DETAILS = mongodb_url
    client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_DETAILS)
    database = client.merakiExplorerDB
    task_collection = database.get_collection("task_collection")
    openAPIspecFiles = database.get_collection("openAPIspecFiles")

# Insert DefaultopenAPIspecFile infos to mongoDB at start

    try:
        if os.getenv('FASTAPI_ENV',    FASTAPI_ENV_DEFAULT) == 'development':
            with open("DefaultopenAPIspecFile.json") as f:
                data = json.load(f)
                DefaultopenAPIspecFile = {
                    "download_date": datetime.now().strftime("%d-%m-%Y %H:%M:%S"),
                    "version": "default",
                    "json_file": data,
                    "file_version": "zcondwzxyo"
                }

                mongoInfo = openAPIspecFiles.find_one_and_replace({"version": "default"},
                                                                  DefaultopenAPIspecFile, upsert=True)
                print("DefaultopenAPIspecFile inserted")
                logging.info("DefaultopenAPIspecFile inserted")
        else:
            with open("back-end/DefaultopenAPIspecFile.json") as f:
                data = json.load(f)
                DefaultopenAPIspecFile = {
                    "download_date": datetime.now().strftime("%d-%m-%Y %H:%M:%S"),
                    "version": "default",
                    "json_file": data,
                    "file_version": "zcondwzxyo"
                }

                mongoInfo = openAPIspecFiles.find_one_and_replace({"version": "default"},
                                                                  DefaultopenAPIspecFile, upsert=True)
                print("DefaultopenAPIspecFile inserted")
                logging.info("DefaultopenAPIspecFile inserted")

    except Exception as err:
        print('err: ', err)
        logging.error(err)
    print("Database connected!", mongodb_url)
    logging.info("Database connected!")
except Exception as error:
    print('DB error: ', error)
    logging.error(error)
    print("Database connection error!")
    logging.error("Database connection error!")
    print('mongodb_url: ', mongodb_url)



# ========================== BASE MODEL ===================================
# =========================================================================
class GetOrganizationsData(BaseModel):
    apiKey: str


class GetNetworksAndDevicesData(BaseModel):
    apiKey: str
    organizationId: str


class GetOpenAPIData(BaseModel):
    file_version: str


class GetOpenAPIupdateData(BaseModel):
    apiKey: str
    organizationId: str


class ApiCallData(BaseModel):
    apiKey: Optional[str] = None
    responseString: Optional[str] = None
    ParameterTemplate: Optional[dict] = None
    ParameterTemplateJSON: Optional[dict] = None
    responsePrefixes: Optional[dict] = None
    useJsonBody: Optional[bool] = None
    organizationIDSelected: Optional[list] = None
    networksIDSelected: Optional[list] = None
    devicesIDSelected: Optional[list] = None
    usefulParameter: Optional[str] = None
    isRollbackActive: Optional[bool] = None
    method: Optional[str] = None
    organization: Optional[str] = None
    requiredParameters: Optional[list] = None


class getAllTasksData(BaseModel):
    test: str


class RollbackData(BaseModel):
    RollbackParameterTemplate: dict


# =========================================================================
# =========================================================================






@ app.get("/", tags=["root"])
async def read_root() -> dict:
    return {"message": "Welcome to Meraki Explorer."}



@ app.post("/GetOrganizations", tags=["GetOrganizations"])
async def GetOrganizations(data: GetOrganizationsData):
    
    dt_string = datetime.now().strftime("%d-%m-%Y %H:%M:%S")
    try:
        logging.info(f"{dt_string} NEW API CALL")
        API_KEY = data.apiKey
        dashboard = meraki.DashboardAPI(
            API_KEY, output_log=False, suppress_logging=False)
        response = dashboard.organizations.getOrganizations()
        logging.info(response)
        
        return response
    except (meraki.APIError, TypeError, KeyError) as err:
        if TypeError:
            logging.error(err.args)
            
            return {"error": err.args}
        if KeyError:
            logging.error(err)
            
            return {"error": err}
        else:
            logging.error(err.status)
            logging.error(err.reason)
            logging.error(err.message)
            

        
        return {'status': err.status, "message": err.message, "error": err.reason}


@ app.post("/GetNetworksAndDevices", tags=["GetNetworksAndDevices"])
async def GetNetworksAndDevices(data: GetNetworksAndDevicesData):
    
    dt_string = datetime.now().strftime("%d-%m-%Y %H:%M:%S")
    try:
        logging.info(f"{dt_string} NEW API CALL")
        API_KEY = data.apiKey
        dashboard = meraki.DashboardAPI(
            API_KEY, output_log=False, suppress_logging=False)
        organizationId = data.organizationId
        networks = dashboard.organizations.getOrganizationNetworks(
            organizationId, total_pages='all')
        devices = dashboard.organizations.getOrganizationInventoryDevices(
            organizationId, total_pages='all')
        logging.info(networks)
        logging.info(devices)
        
        return {"networks": networks, "devices": devices}
    except (meraki.APIError, TypeError, KeyError) as err:
        if TypeError:
            logging.error(err.args)
            
            return {"error": err.args}
        if KeyError:
            logging.error(err)
            
            return {"error": err}
        else:
            logging.error(err.status)
            logging.error(err.reason)
            logging.error(err.message)
            

        
        return {'status': err.status, "message": err.message, "error": err.reason}


@ app.post("/GetOpenAPI", tags=["GetOpenAPI"])
async def GetOpenAPI(data: GetOpenAPIData):
    
    dt_string = datetime.now().strftime("%d-%m-%Y %H:%M:%S")
    file_version = data.file_version
    try:
        new_version = await database.openAPIspecFiles.find_one({"file_version": file_version}, {'_id': False})
        return {"new_version": new_version}

    except Exception as err:
        logging.error(err)
        return {"error": "there was an error uploading the file"}


@ app.get("/GetAllOpenAPI", tags=["GetAllOpenAPI"])
async def GetAllOpenAPI():
    dt_string = datetime.now().strftime("%d-%m-%Y %H:%M:%S")
    try:
        # get all file Infos from mongoDB
        cursor = database.openAPIspecFiles.find({}, {'_id': False})
        cursorList = await cursor.to_list(None)
        return {"allOpenAPIinfo": cursorList}

    except Exception as err:
        logging.error(err)
        return {"error": "there was an error uploading the file"}


@ app.post("/GetOpenAPIupdate", tags=["GetOpenAPIupdate"])
async def GetOpenAPIupdate(data: GetOpenAPIupdateData):
    
    dt_string = datetime.now().strftime("%d-%m-%Y %H:%M:%S")
    date_string = datetime.now().strftime("%d-%m-%Y")
    filename_date = datetime.now().strftime("%Y%m%d%H%M%S")
    try:
        logging.info(f"{dt_string} NEW API CALL")
        API_KEY = data.apiKey
        dashboard = meraki.DashboardAPI(
            API_KEY, output_log=False, suppress_logging=False)
        organizationId = data.organizationId

        openAPI = dashboard.organizations.getOrganizationOpenapiSpec(
            organizationId)

        

        # save openAPIspecFile infos to mongoDB
        try:

            openAPIspecFileCollection = {
                "download_date": dt_string,
                "version": openAPI["info"]["version"],
                "json_file": openAPI,
                "file_version": ''.join(random.choice(string.ascii_lowercase) for i in range(10))
            }

            mongoInfo = await openAPIspecFiles.insert_one(openAPIspecFileCollection)

            # get all file Infos from mongoDB
            cursor = database.openAPIspecFiles.find({}, {'_id': False})

            cursorList = await cursor.to_list(None)
            #####ä###
            # remove oldest file (but not the default), keep only 10 files
            if len(cursorList) > 10:
                last = database.openAPIspecFiles.find().sort(
                    [('_id', 1)]).limit(2)
                docs = await last.to_list(None)
                docDelete = await database.openAPIspecFiles.find_one_and_delete({"_id": docs[1]['_id']})
                cursorAfterDelete = database.openAPIspecFiles.find(
                    {}, {'_id': False})
                cursorListAfterDelete = await cursorAfterDelete.to_list(None)
                allOpenAPIinfoAfterDelete = json.loads(
                    json_util.dumps(cursorListAfterDelete))
                return {"info": "openAPIspec file uploaded",  "allOpenAPIinfo": allOpenAPIinfoAfterDelete}
            else:
                allOpenAPIinfo = json.loads(json_util.dumps(cursorList))
                return {"info": "openAPIspec file uploaded",  "allOpenAPIinfo": allOpenAPIinfo}
        except Exception as err:
            logging.error(err)
            return {"error": "there was an error uploading the file"}

    except (meraki.APIError, TypeError, KeyError) as err:
        if TypeError:
            logging.error(err.args)
            
            return {"error": err.args}
        if KeyError:
            logging.error(err)
            
            return {"error": err}
        else:
            logging.error(err.status)
            logging.error(err.reason)
            logging.error(err.message)
            

        
        return {'status': err.status, "message": err.message, "error": err.reason}


@ app.post("/ApiCall", tags=["ApiCall"])
async def ApiCall(data: ApiCallData):
    now = datetime.now()
    
    dt_string = now.strftime("%d-%m-%Y %H:%M:%S")
    organization = data.organization
    if data.useJsonBody == False:
        if data.usefulParameter == "networkId":
            if data.isRollbackActive == True:
                try:
                    logging.info(f"{dt_string} NEW API CALL")
                    API_KEY = data.apiKey
                    dashboard = meraki.DashboardAPI(
                        API_KEY, output_log=False, suppress_logging=False)

                    category = data.responsePrefixes["category"]
                    rollbackId = data.responsePrefixes["rollbackId"]
                    NetworkList = data.networksIDSelected
                    parameter = data.ParameterTemplate
                    requiredParameters = data.requiredParameters
                    NetworkResults = []
                    RollbackResponse = []

                    # get only required parameter in get-rollbackId
                    rollbackGetparameters = dict()
                    for (key, value) in parameter.items():
                        if key in requiredParameters:
                            rollbackGetparameters[key] = value

                    if len(data.networksIDSelected) == 0:
                        if "," in parameter["networkId"]:
                            # remove all whitespace characters (space, tab, newline, and so on)
                            noSpaces = ''.join(
                                parameter["networkId"].split())
                            # split in array by comma
                            networkIdArray = noSpaces.split(",")
                            for index, networkId in enumerate(networkIdArray):
                                result = getattr(
                                    getattr(dashboard, category), rollbackId)(**rollbackGetparameters)
                                logging.info(result)
                                RollbackResponse.append(result)
                                RollbackResponse[index]["networkId"] = networkId
                                
                            logging.info(RollbackResponse)
                        else:
                            networkId = parameter["networkId"]
                            RollbackResponse = getattr(
                                getattr(dashboard, category), rollbackId)(**rollbackGetparameters)
                            RollbackResponse["networkId"] = networkId
                            
                            logging.info(RollbackResponse)

                    else:
                        for index, networkId in enumerate(NetworkList):

                            result = getattr(
                                getattr(dashboard, category), rollbackId)(**rollbackGetparameters)
                            RollbackResponse.append(result)
                            RollbackResponse[index]["networkId"] = networkId
                            logging.info(result)
                            NetworkResults.append(result)
                            

                        logging.info(NetworkResults)

                except (meraki.APIError, TypeError, KeyError) as err:
                    if TypeError:
                        logging.error(err.args)
                        
                        taskCollection = {
                            "task_name": rollbackId,
                            "start_time": dt_string,
                            "organization": organization,
                            "usefulParameter": data.usefulParameter,
                            "category": category,
                            "method": data.method,
                            "rollback": data.isRollbackActive,
                            "parameter": "",

                            "response": err.args,
                            "rollback_response": RollbackResponse,
                            "error": True
                        }
                        task = await task_collection.insert_one(taskCollection)
                        return {"error": err.args}
                    if KeyError:
                        logging.error(err)
                        
                        taskCollection = {
                            "task_name": rollbackId,
                            "start_time": dt_string,
                            "organization": organization,
                            "usefulParameter": data.usefulParameter,
                            "category": category,
                            "method": data.method,
                            "rollback": data.isRollbackActive,
                            "parameter": "",

                            "response": err,
                            "rollback_response": RollbackResponse,
                            "error": True
                        }
                        task = await task_collection.insert_one(taskCollection)
                        return {"error": err}
                    else:
                        logging.error(err.status)
                        logging.error(err.reason)
                        logging.error(err.message)
                        
                        taskCollection = {
                            "task_name": rollbackId,
                            "start_time": dt_string,
                            "organization": organization,
                            "usefulParameter": data.usefulParameter,
                            "category": category,
                            "method": data.method,
                            "rollback": data.isRollbackActive,
                            "parameter": "",

                            "response": err.reason,
                            "rollback_response": RollbackResponse,
                            "error": True
                        }
                        task = await task_collection.insert_one(taskCollection)

                    
                    return {'status': err.status, "message": err.message, "error": err.reason}

                try:
                    logging.info(f"{dt_string} NEW API CALL")
                    API_KEY = data.apiKey
                    dashboard = meraki.DashboardAPI(
                        API_KEY, output_log=False, suppress_logging=False)

                    category = data.responsePrefixes["category"]
                    operationId = data.responsePrefixes["operationId"]
                    parameter = data.ParameterTemplate
                    loop_parameter = []

                    if len(data.networksIDSelected) == 0:
                        if "," in parameter["networkId"]:
                            # remove all whitespace characters (space, tab, newline, and so on)
                            noSpaces = ''.join(
                                parameter["networkId"].split())
                            # split in array by comma
                            networkIdArray = noSpaces.split(",")
                            # remove networkId because already passed in the networkIdArray, keep other parameters
                            parameter.pop("networkId")
                            NetworkResults = []
                            for networkId in networkIdArray:
                                result = getattr(getattr(dashboard, category), operationId)(
                                    networkId, **parameter)
                                loop_parameter.append(
                                    {"networkId": networkId, **parameter})
                                logging.info(result)
                                NetworkResults.append(result)
                                
                            taskCollection = {"task_name": operationId,
                                                "start_time": dt_string,
                                                "organization": organization,
                                                "usefulParameter": data.usefulParameter,
                                                "category": category,
                                                "method": data.method,
                                                "rollback": data.isRollbackActive,
                                                "parameter": loop_parameter,
                                                "response": NetworkResults,
                                                "error": False}
                            task = await task_collection.insert_one(taskCollection)
                            return NetworkResults
                        else:
                            result = getattr(
                                getattr(dashboard, category), operationId)(**parameter)
                            logging.info(result)
                            
                            taskCollection = {"task_name": operationId,
                                                "start_time": dt_string,
                                                "organization": organization,
                                                "usefulParameter": data.usefulParameter,
                                                "category": category,
                                                "method": data.method,
                                                "rollback": data.isRollbackActive,
                                                "parameter": parameter,
                                                "response": result,
                                                "error": False}
                            task = await task_collection.insert_one(taskCollection)
                            return result
                    else:
                        # remove networkId because already passed in the loop, keep other parameters
                        parameter.pop("networkId")
                        NetworkList = data.networksIDSelected
                        NetworkResults = []
                        for networkId in NetworkList:
                            result = getattr(getattr(dashboard, category), operationId)(
                                networkId, **parameter)
                            loop_parameter.append(
                                {"networkId": networkId, **parameter})
                            logging.info(result)
                            NetworkResults.append(result)
                            
                        taskCollection = {
                            "task_name": operationId,
                            "start_time": dt_string,
                            "organization": organization,
                            "usefulParameter": data.usefulParameter,
                            "category": category,
                            "method": data.method,
                            "rollback": data.isRollbackActive,
                            "parameter": loop_parameter,

                            "response": NetworkResults,
                            "rollback_response": RollbackResponse,
                            "error": False
                        }
                        task = await task_collection.insert_one(taskCollection)

                        return NetworkResults

                except (meraki.APIError, TypeError, KeyError) as err:
                    if TypeError:
                        logging.error(err.args)
                        
                        taskCollection = {
                            "task_name": operationId,
                            "start_time": dt_string,
                            "organization": organization,
                            "usefulParameter": data.usefulParameter,
                            "category": category,
                            "method": data.method,
                            "rollback": data.isRollbackActive,
                            "parameter": loop_parameter,

                            "response": err.args,
                            "rollback_response": RollbackResponse,
                            "error": True
                        }
                        task = await task_collection.insert_one(taskCollection)
                        return {"error": err.args}
                    if KeyError:
                        logging.error(err)
                        
                        taskCollection = {
                            "task_name": operationId,
                            "start_time": dt_string,
                            "organization": organization,
                            "usefulParameter": data.usefulParameter,
                            "category": category,
                            "method": data.method,
                            "rollback": data.isRollbackActive,
                            "parameter": loop_parameter,

                            "response": err,
                            "rollback_response": RollbackResponse,
                            "error": True
                        }
                        task = await task_collection.insert_one(taskCollection)
                        return {"error": err}
                    else:
                        logging.error(err.status)
                        logging.error(err.reason)
                        logging.error(err.message)
                        taskCollection = {
                            "task_name": operationId,
                            "start_time": dt_string,
                            "organization": organization,
                            "usefulParameter": data.usefulParameter,
                            "category": category,
                            "method": data.method,
                            "rollback": data.isRollbackActive,
                            "parameter": loop_parameter,

                            "response": err.reason,
                            "rollback_response": RollbackResponse,
                            "error": True
                        }
                        task = await task_collection.insert_one(taskCollection)
                        

                    
                    return {'status': err.status, "message": err.message, "error": err.reason}
            elif data.isRollbackActive == False:
                try:
                    logging.info(f"{dt_string} NEW API CALL")
                    API_KEY = data.apiKey
                    dashboard = meraki.DashboardAPI(
                        API_KEY, output_log=False, suppress_logging=False)

                    category = data.responsePrefixes["category"]
                    operationId = data.responsePrefixes["operationId"]
                    parameter = data.ParameterTemplate
                    loop_parameter = []

                    if len(data.networksIDSelected) == 0:
                        if "," in parameter["networkId"]:
                            # remove all whitespace characters (space, tab, newline, and so on)
                            noSpaces = ''.join(
                                parameter["networkId"].split())
                            # split in array by comma
                            networkIdArray = noSpaces.split(",")
                            # remove networkId because already passed in the networkIdArray, keep other parameters
                            parameter.pop("networkId")
                            NetworkResults = []
                            for networkId in networkIdArray:
                                result = getattr(getattr(dashboard, category), operationId)(
                                    networkId, **parameter)
                                loop_parameter.append(
                                    {"networkId": networkId, **parameter})
                                logging.info(result)
                                NetworkResults.append(result)
                                
                            taskCollection = {"task_name": operationId,
                                                "start_time": dt_string,
                                                "organization": organization,
                                                "usefulParameter": data.usefulParameter,
                                                "category": category,
                                                "method": data.method,
                                                "rollback": data.isRollbackActive,
                                                "parameter": loop_parameter,
                                                "response": NetworkResults,
                                                "error": False}
                            task = await task_collection.insert_one(taskCollection)
                            logging.info(NetworkResults)
                            return NetworkResults
                        else:
                            result = getattr(
                                getattr(dashboard, category), operationId)(**parameter)
                            logging.info(result)
                            
                            taskCollection = {"task_name": operationId,
                                                "start_time": dt_string,
                                                "organization": organization,
                                                "usefulParameter": data.usefulParameter,
                                                "category": category,
                                                "method": data.method,
                                                "rollback": data.isRollbackActive,
                                                "parameter": parameter,
                                                "response": result,
                                                "error": False}
                            task = await task_collection.insert_one(taskCollection)
                            return result

                    else:
                        # remove networkId because already passed in the loop, keep other parameters
                        parameter.pop("networkId")
                        NetworkList = data.networksIDSelected
                        NetworkResults = []

                        for networkId in NetworkList:
                            result = getattr(getattr(dashboard, category), operationId)(
                                networkId, **parameter)
                            loop_parameter.append(
                                {"networkId": networkId, **parameter})
                            logging.info(result)
                            NetworkResults.append(result)
                            

                        taskCollection = {"task_name": operationId,
                                            "start_time": dt_string,
                                            "organization": organization,
                                            "usefulParameter": data.usefulParameter,
                                            "category": category,
                                            "method": data.method,
                                            "rollback": data.isRollbackActive,
                                            "parameter": loop_parameter,

                                            "response": NetworkResults,
                                            "error": False}
                        task = await task_collection.insert_one(taskCollection)

                        return NetworkResults

                except (meraki.APIError, TypeError, KeyError) as err:
                    if TypeError:
                        logging.error(err.args)
                        
                        taskCollection = {"task_name": operationId,
                                            "start_time": dt_string,
                                            "organization": organization,
                                            "usefulParameter": data.usefulParameter,
                                            "category": category,
                                            "method": data.method,
                                            "rollback": data.isRollbackActive,
                                            "parameter": loop_parameter,

                                            "response": err.args,
                                            "error": True}
                        task = await task_collection.insert_one(taskCollection)
                        return {"error": err.args}
                    if KeyError:
                        logging.error(err)
                        
                        taskCollection = {"task_name": operationId,
                                            "start_time": dt_string,
                                            "organization": organization,
                                            "usefulParameter": data.usefulParameter,
                                            "category": category,
                                            "method": data.method,
                                            "rollback": data.isRollbackActive,
                                            "parameter": loop_parameter,
                                            "response": err,
                                            "error": True}
                        task = await task_collection.insert_one(taskCollection)
                        return {"error": err}
                    else:
                        logging.error(err.status)
                        logging.error(err.reason)
                        logging.error(err.message)
                        taskCollection = {"task_name": operationId,
                                            "start_time": dt_string,
                                            "organization": organization,
                                            "usefulParameter": data.usefulParameter,
                                            "category": category,
                                            "method": data.method,
                                            "rollback": data.isRollbackActive,
                                            "parameter": loop_parameter,

                                            "response": err.reason,
                                            "error": True}
                        task = await task_collection.insert_one(taskCollection)
                        

                    
                    return {'status': err.status, "message": err.message, "error": err.reason}

        elif data.usefulParameter == "serial":
            if data.isRollbackActive == True:
                try:
                    logging.info(f"{dt_string} NEW API CALL")
                    API_KEY = data.apiKey
                    dashboard = meraki.DashboardAPI(
                        API_KEY, output_log=False, suppress_logging=False,retry_4xx_error=True,retry_4xx_error_wait_time=3,maximum_retries=2)

                    category = data.responsePrefixes["category"]
                    rollbackId = data.responsePrefixes["rollbackId"]
                    DevicesList = data.devicesIDSelected
                    parameter = data.ParameterTemplate
                    requiredParameters = data.requiredParameters
                    DeviceResults = []
                    RollbackResponse = []

                    # get only required parameter in get-rollbackId
                    rollbackGetparameters = dict()
                    for (key, value) in parameter.items():
                        if key in requiredParameters:
                            rollbackGetparameters[key] = value

                    if len(data.devicesIDSelected) == 0:
                        if "," in parameter["serial"]:
                            # remove all whitespace characters (space, tab, newline, and so on)
                            noSpaces = ''.join(parameter["serial"].split())
                            # split in array by comma
                            serialArray = noSpaces.split(",")
                            for index, serial in enumerate(serialArray):
                                try:
                                    result = getattr(
                                        getattr(dashboard, category), rollbackId)(**rollbackGetparameters)
                                    logging.info(result)
                                    RollbackResponse.append(result)
                                    RollbackResponse[index]["serial"] = serial
                                except (meraki.APIError,TypeError, KeyError, meraki.APIKeyError, ValueError) as err:
                                    RollbackResponse.append({"error": {"serial" : serial,"msg": str(err), "status": err.status}})
                                    if err.status == 401 | 404 | 403:
                                        logging.error({"error": {"serial" : serial,"msg": str(err), "status": err.status}})
                                        continue
                                
                            logging.info(RollbackResponse)
                        else:
                            try:
                                serial = parameter["serial"]
                                RollbackResponse = getattr(
                                    getattr(dashboard, category), rollbackId)(**rollbackGetparameters)
                                RollbackResponse["serial"] = serial
                                logging.info(RollbackResponse)
                            except (meraki.APIError,TypeError, KeyError, meraki.APIKeyError, ValueError) as err:
                                RollbackResponse = ({"error": {"serial" : serial,"msg": str(err), "status": err.status}})
                                if err.status == 401 | 404 | 403:
                                    logging.error({"error": {"serial" : serial,"msg": str(err), "status": err.status}})

                    else:
                        for index, serial in enumerate(DevicesList):
                            try:
                                result = getattr(
                                    getattr(dashboard, category), rollbackId)(**rollbackGetparameters)
                                RollbackResponse.append(result)
                                RollbackResponse[index]["serial"] = serial
                                logging.info(result)
                                DeviceResults.append(result)
                            except (meraki.APIError,TypeError, KeyError, meraki.APIKeyError, ValueError) as err:
                                RollbackResponse.append({"error": {"serial" : serial,"msg": str(err), "status": err.status}})
                                if err.status == 401 | 404 | 403:
                                    logging.error({"error": {"serial" : serial,"msg": str(err), "status": err.status}})
                                    continue
                            
                        logging.info(DeviceResults)

                except (meraki.APIError, TypeError, KeyError) as err:
                    if TypeError:
                        logging.error(err.args)
                        
                        taskCollection = {
                            "task_name": rollbackId,
                            "start_time": dt_string,
                            "organization": organization,
                            "usefulParameter": data.usefulParameter,
                            "category": category,
                            "method": data.method,
                            "rollback": data.isRollbackActive,
                            "parameter": "",

                            "response": err.args,
                            "rollback_response": RollbackResponse,
                            "error": True
                        }
                        task = await task_collection.insert_one(taskCollection)
                        return {"error": err.args}
                    if KeyError:
                        logging.error(err)
                        
                        taskCollection = {
                            "task_name": rollbackId,
                            "start_time": dt_string,
                            "organization": organization,
                            "usefulParameter": data.usefulParameter,
                            "category": category,
                            "method": data.method,
                            "rollback": data.isRollbackActive,
                            "parameter": "",

                            "response": err,
                            "rollback_response": RollbackResponse,
                            "error": True
                        }
                        task = await task_collection.insert_one(taskCollection)
                        return {"error": err}
                    else:
                        logging.error(err.status)
                        logging.error(err.reason)
                        logging.error(err.message)
                        
                        taskCollection = {
                            "task_name": rollbackId,
                            "start_time": dt_string,
                            "organization": organization,
                            "usefulParameter": data.usefulParameter,
                            "category": category,
                            "method": data.method,
                            "rollback": data.isRollbackActive,
                            "parameter": "",

                            "response": err.reason,
                            "rollback_response": RollbackResponse,
                            "error": True
                        }
                        task = await task_collection.insert_one(taskCollection)

                    
                    return {'status': err.status, "message": err.message, "error": err.reason}
                try:
                    logging.info(f"{dt_string} NEW API CALL")
                    API_KEY = data.apiKey
                    dashboard = meraki.DashboardAPI(
                        API_KEY, output_log=False, suppress_logging=False)

                    category = data.responsePrefixes["category"]
                    operationId = data.responsePrefixes["operationId"]
                    parameter = data.ParameterTemplate
                    loop_parameter = []

                    if len(data.devicesIDSelected) == 0:
                        if "," in parameter["serial"]:
                            # remove all whitespace characters (space, tab, newline, and so on)
                            noSpaces = ''.join(parameter["serial"].split())
                            # split in array by comma
                            serialArray = noSpaces.split(",")
                            # remove serial because already passed in the serialArray, keep other parameters
                            parameter.pop("serial")
                            DeviceResults = []
                            for serial in serialArray:
                                try:
                                    result = getattr(getattr(dashboard, category), operationId)(
                                        serial, **parameter)
                                    loop_parameter.append(
                                        {"serial": serial, **parameter})
                                    logging.info(result)
                                    DeviceResults.append(result)
                                except (meraki.APIError,TypeError, KeyError, meraki.APIKeyError, ValueError) as err:
                                    DeviceResults.append({"error": {"serial" : serial,"msg": str(err), "status": err.status}})
                                    if err.status == 401 | 404 | 403:
                                        logging.error({"error": {"serial" : serial,"msg": str(err), "status": err.status}})
                                        continue
                                
                            taskCollection = {"task_name": operationId,
                                                "start_time": dt_string,
                                                "organization": organization,
                                                "usefulParameter": data.usefulParameter,
                                                "category": category,
                                                "method": data.method,
                                                "rollback": data.isRollbackActive,
                                                "parameter": loop_parameter,
                                                "response": DeviceResults,
                                                "error": False}
                            task = await task_collection.insert_one(taskCollection)
                            return DeviceResults

                        else:
                            try:
                                result = getattr(
                                    getattr(dashboard, category), operationId)(**parameter)
                                logging.info(result)
                                
                                taskCollection = {"task_name": operationId,
                                                    "start_time": dt_string,
                                                    "organization": organization,
                                                    "usefulParameter": data.usefulParameter,
                                                    "category": category,
                                                    "method": data.method,
                                                    "rollback": data.isRollbackActive,
                                                    "parameter": parameter,
                                                    "response": result,
                                                    "error": False}
                                task = await task_collection.insert_one(taskCollection)
                                return result
                            except (meraki.APIError,TypeError, KeyError, meraki.APIKeyError, ValueError) as err:
                                if err.status == 401 | 404 | 403:
                                    result = {"error": {"serial" : parameter["serial"],"msg": str(err), "status": err.status}}
                                    logging.error(result)
                                return {"error": {"serial" : parameter["serial"],"msg": str(err), "status": err.status}}


                    else:
                        # remove serial because already passed in the loop, keep other parameters
                        parameter.pop("serial")
                        DevicesList = data.devicesIDSelected
                        DeviceResults = []
                        for serial in DevicesList:
                            try:
                                result = getattr(getattr(dashboard, category), operationId)(
                                    serial, **parameter)
                                loop_parameter.append(
                                    {"serial": serial, **parameter})
                                DeviceResults.append(result)
                            except (meraki.APIError,TypeError, KeyError, meraki.APIKeyError, ValueError) as err:
                                DeviceResults.append({"error": {"serial" : serial,"msg": str(err), "status": err.status}})
                                if err.status == 401 | 404 | 403:
                                    logging.error({"error": {"serial" : serial,"msg": str(err), "status": err.status}})
                                    continue
                            
                        taskCollection = {
                            "task_name": operationId,
                            "start_time": dt_string,
                            "organization": organization,
                            "usefulParameter": data.usefulParameter,
                            "category": category,
                            "method": data.method,
                            "rollback": data.isRollbackActive,
                            "parameter": loop_parameter,

                            "response": DeviceResults,
                            "rollback_response": RollbackResponse,
                            "error": False
                        }
                        task = await task_collection.insert_one(taskCollection)
                        return DeviceResults

                except (meraki.APIError, TypeError, KeyError) as err:
                    if TypeError:
                        logging.error(err.args)
                        
                        taskCollection = {
                            "task_name": operationId,
                            "start_time": dt_string,
                            "organization": organization,
                            "usefulParameter": data.usefulParameter,
                            "category": category,
                            "method": data.method,
                            "rollback": data.isRollbackActive,
                            "parameter": loop_parameter,

                            "response": err.args,
                            "rollback_response": RollbackResponse,
                            "error": True
                        }
                        task = await task_collection.insert_one(taskCollection)
                        return {"error": err.args}
                    if KeyError:
                        logging.error(err)
                        
                        taskCollection = {
                            "task_name": operationId,
                            "start_time": dt_string,
                            "organization": organization,
                            "usefulParameter": data.usefulParameter,
                            "category": category,
                            "method": data.method,
                            "rollback": data.isRollbackActive,
                            "parameter": loop_parameter,

                            "response": err,
                            "rollback_response": RollbackResponse,
                            "error": True
                        }
                        task = await task_collection.insert_one(taskCollection)
                        return {"error": err}
                    else:
                        logging.error(err.status)
                        logging.error(err.reason)
                        logging.error(err.message)
                        taskCollection = {
                            "task_name": operationId,
                            "start_time": dt_string,
                            "organization": organization,
                            "usefulParameter": data.usefulParameter,
                            "category": category,
                            "method": data.method,
                            "rollback": data.isRollbackActive,
                            "parameter": loop_parameter,

                            "response": err.reason,
                            "rollback_response": RollbackResponse,
                            "error": True
                        }
                        task = await task_collection.insert_one(taskCollection)
                        

                    
                    return {'status': err.status, "message": err.message, "error": err.reason}
            elif data.isRollbackActive == False:
                try:
                    logging.info(f"{dt_string} NEW API CALL")
                    API_KEY = data.apiKey
                    dashboard = meraki.DashboardAPI(
                        API_KEY, output_log=False, suppress_logging=False,retry_4xx_error=True,retry_4xx_error_wait_time=3,maximum_retries=2)

                    category = data.responsePrefixes["category"]
                    operationId = data.responsePrefixes["operationId"]
                    parameter = data.ParameterTemplate
                    loop_parameter = []

                    if len(data.devicesIDSelected) == 0:
                        if "," in parameter["serial"]:
                            # remove all whitespace characters (space, tab, newline, and so on)
                            noSpaces = ''.join(parameter["serial"].split())
                            # split in array by comma
                            serialArray = noSpaces.split(",")
                            # remove serial because already passed in the SerialArray, keep other parameters
                            parameter.pop("serial")
                            DeviceResults = []
                            for serial in serialArray:
                                try:
                                    result = getattr(getattr(dashboard, category), operationId)(
                                        serial, **parameter)
                                    loop_parameter.append(
                                        {"serial": serial, **parameter})
                                    logging.info(result)
                                    DeviceResults.append(result)
                                except (meraki.APIError,TypeError, KeyError, meraki.APIKeyError, ValueError) as err:
                                    DeviceResults.append({"error": {"serial" : serial,"msg": str(err), "status": err.status}})
                                    if err.status == 401 | 404 | 403:
                                        logging.error({"error": {"serial" : serial,"msg": str(err), "status": err.status}})
                                        continue
                                
                            taskCollection = {"task_name": operationId,
                                                "start_time": dt_string,
                                                "organization": organization,
                                                "usefulParameter": data.usefulParameter,
                                                "category": category,
                                                "method": data.method,
                                                "rollback": data.isRollbackActive,
                                                "parameter": loop_parameter,
                                                "response": DeviceResults,
                                                "error": False}
                            task = await task_collection.insert_one(taskCollection)
                            return DeviceResults


                        else:
                            try:
                                result = getattr(
                                    getattr(dashboard, category), operationId)(**parameter)
                                logging.info(result)
                                
                                taskCollection = {"task_name": operationId,
                                                    "start_time": dt_string,
                                                    "organization": organization,
                                                    "usefulParameter": data.usefulParameter,
                                                    "category": category,
                                                    "method": data.method,
                                                    "rollback": data.isRollbackActive,
                                                    "parameter": parameter,
                                                    "response": result,
                                                    "error": False}
                                task = await task_collection.insert_one(taskCollection)
                                
                                return result
                            except (meraki.APIError,TypeError, KeyError, meraki.APIKeyError, ValueError) as err:
                                if err.status == 401 | 404 | 403:
                                    result = {"error": {"serial" : parameter["serial"],"msg": str(err), "status": err.status}}
                                    logging.error(result)
                                return {"error": {"serial" : parameter["serial"],"msg": str(err), "status": err.status}}

                    else:
                        # remove serial because already passed in the loop, keep other parameters
                        parameter.pop("serial")
                        DevicesList = data.devicesIDSelected
                        DeviceResults = []
                        for serial in DevicesList:
                            try:
                                result = getattr(getattr(dashboard, category), operationId)(
                                    serial, **parameter)
                                loop_parameter.append(
                                    {"serial": serial, **parameter})
                                logging.info(result)
                                DeviceResults.append(result)
                            except (meraki.APIError,TypeError, KeyError, meraki.APIKeyError, ValueError) as err:
                                DeviceResults.append({"error": {"serial" : serial,"msg": str(err), "status": err.status}})
                                if err.status == 401 | 404 | 403:
                                    logging.error({"error": {"serial" : serial,"msg": str(err), "status": err.status}})
                                    continue
                            
                        taskCollection = {"task_name": operationId,
                                            "start_time": dt_string,
                                            "organization": organization,
                                            "usefulParameter": data.usefulParameter,
                                            "category": category,
                                            "method": data.method,
                                            "rollback": data.isRollbackActive,
                                            "parameter": loop_parameter,
                                            "response": DeviceResults,
                                            "error": False}
                        task = await task_collection.insert_one(taskCollection)
                        return DeviceResults

                except (meraki.APIError, TypeError, KeyError) as err:
                    if TypeError:
                        logging.error(err.args)
                        
                        taskCollection = {"task_name": operationId,
                                            "start_time": dt_string,
                                            "organization": organization,
                                            "usefulParameter": data.usefulParameter,
                                            "category": category,
                                            "method": data.method,
                                            "rollback": data.isRollbackActive,
                                            "parameter": loop_parameter,
                                            "response": err.args,
                                            "error": True}
                        task = await task_collection.insert_one(taskCollection)
                        return {"error": err.args}
                    if KeyError:
                        logging.error(err)
                        
                        taskCollection = {"task_name": operationId,
                                            "start_time": dt_string,
                                            "organization": organization,
                                            "usefulParameter": data.usefulParameter,
                                            "category": category,
                                            "method": data.method,
                                            "rollback": data.isRollbackActive,
                                            "parameter": loop_parameter,
                                            "response": err,
                                            "error": True}
                        task = await task_collection.insert_one(taskCollection)
                        return {"error": err}
                    else:
                        logging.error(err.status)
                        logging.error(err.reason)
                        logging.error(err.message)
                        
                        taskCollection = {"task_name": operationId,
                                            "start_time": dt_string,
                                            "organization": organization,
                                            "usefulParameter": data.usefulParameter,
                                            "category": category,
                                            "method": data.method,
                                            "rollback": data.isRollbackActive,
                                            "parameter": loop_parameter,

                                            "response": err.reason,
                                            "error": True}
                        task = await task_collection.insert_one(taskCollection)

                    
                    return {'status': err.status, "message": err.message, "error": err.reason}
        if data.usefulParameter == "organizationId":
            if data.isRollbackActive == True:
                try:
                    logging.info(f"{dt_string} NEW API CALL")
                    API_KEY = data.apiKey
                    dashboard = meraki.DashboardAPI(
                        API_KEY, output_log=False, suppress_logging=False)

                    category = data.responsePrefixes["category"]
                    rollbackId = data.responsePrefixes["rollbackId"]
                    OrganizationList = data.organizationIDSelected
                    parameter = data.ParameterTemplate
                    requiredParameters = data.requiredParameters
                    OrganizationResults = []
                    RollbackResponse = []

                    # get only required parameter in get-rollbackId
                    rollbackGetparameters = dict()
                    for (key, value) in parameter.items():
                        if key in requiredParameters:
                            rollbackGetparameters[key] = value

                    if len(data.organizationIDSelected) == 0:
                        if "," in parameter["organizationId"]:
                            # remove all whitespace characters (space, tab, newline, and so on)
                            noSpaces = ''.join(
                                parameter["organizationId"].split())
                            # split in array by comma
                            organizationIdArray = noSpaces.split(",")
                            for index, organizationId in enumerate(organizationIdArray):
                                result = getattr(
                                    getattr(dashboard, category), rollbackId)(**rollbackGetparameters)
                                logging.info(result)
                                RollbackResponse.append(result)
                                RollbackResponse[index]["organizationId"] = organizationId
                                
                            logging.info(RollbackResponse)
                        else:
                            organizationId = parameter["organizationId"]
                            RollbackResponse = getattr(
                                getattr(dashboard, category), rollbackId)(**rollbackGetparameters)
                            RollbackResponse["organizationId"] = organizationId
                            
                            logging.info(RollbackResponse)

                    else:
                        for index, organizationId in enumerate(OrganizationList):
                            result = getattr(
                                getattr(dashboard, category), rollbackId)(**rollbackGetparameters)
                            RollbackResponse.append(result)
                            RollbackResponse[index]["organizationId"] = organizationId
                            logging.info(result)
                            OrganizationResults.append(result)
                            

                        logging.info(OrganizationResults)

                except (meraki.APIError, TypeError, KeyError, AttributeError) as err:
                    if TypeError:
                        logging.error(err.args)
                        
                        taskCollection = {
                            "task_name": rollbackId,
                            "start_time": dt_string,
                            "organization": organization,
                            "usefulParameter": data.usefulParameter,
                            "category": category,
                            "method": data.method,
                            "rollback": data.isRollbackActive,
                            "parameter": "",

                            "response": err.args,
                            "rollback_response": RollbackResponse,
                            "error": True
                        }
                        task = await task_collection.insert_one(taskCollection)
                        return {"error": err.args}
                    if KeyError:
                        logging.error(err)
                        
                        taskCollection = {
                            "task_name": rollbackId,
                            "start_time": dt_string,
                            "organization": organization,
                            "usefulParameter": data.usefulParameter,
                            "category": category,
                            "method": data.method,
                            "rollback": data.isRollbackActive,
                            "parameter": "",

                            "response": err,
                            "rollback_response": RollbackResponse,
                            "error": True
                        }
                        task = await task_collection.insert_one(taskCollection)
                        return {"error": err}
                    if AttributeError:
                        logging.error(err)
                        
                        taskCollection = {
                            "task_name": rollbackId,
                            "start_time": dt_string,
                            "organization": organization,
                            "usefulParameter": data.usefulParameter,
                            "category": category,
                            "method": data.method,
                            "rollback": data.isRollbackActive,
                            "parameter": "",

                            "response": err,
                            "rollback_response": RollbackResponse,
                            "error": True
                        }
                        task = await task_collection.insert_one(taskCollection)
                        return {"error": err}
                    else:
                        logging.error(err.status)
                        logging.error(err.reason)
                        logging.error(err.message)
                        
                        taskCollection = {
                            "task_name": rollbackId,
                            "start_time": dt_string,
                            "organization": organization,
                            "usefulParameter": data.usefulParameter,
                            "category": category,
                            "method": data.method,
                            "rollback": data.isRollbackActive,
                            "parameter": "",

                            "response": err.reason,
                            "rollback_response": RollbackResponse,
                            "error": True
                        }
                        task = await task_collection.insert_one(taskCollection)

                    
                    return {'status': err.status, "message": err.message, "error": err.reason}

                try:
                    logging.info(f"{dt_string} NEW API CALL")
                    API_KEY = data.apiKey
                    dashboard = meraki.DashboardAPI(
                        API_KEY, output_log=False, suppress_logging=False)

                    category = data.responsePrefixes["category"]
                    operationId = data.responsePrefixes["operationId"]
                    parameter = data.ParameterTemplate
                    loop_parameter = []

                    if len(data.organizationIDSelected) == 0:
                        if "," in parameter["organizationId"]:
                            # remove all whitespace characters (space, tab, newline, and so on)
                            noSpaces = ''.join(
                                parameter["organizationId"].split())
                            # split in array by comma
                            organizationIdArray = noSpaces.split(",")
                            # remove organizationId because already passed in the organizationIdArray, keep other parameters
                            parameter.pop("organizationId")
                            OrganizationResults = []
                            for organizationId in organizationIdArray:
                                result = getattr(getattr(dashboard, category), operationId)(
                                    organizationId, **parameter)
                                loop_parameter.append(
                                    {"organizationId": organizationId, **parameter})
                                logging.info(result)
                                OrganizationResults.append(result)
                                
                            taskCollection = {"task_name": operationId,
                                                "start_time": dt_string,
                                                "organization": organization,
                                                "usefulParameter": data.usefulParameter,
                                                "category": category,
                                                "method": data.method,
                                                "rollback": data.isRollbackActive,
                                                "parameter": loop_parameter,
                                                "response": OrganizationResults,
                                                "error": False}
                            task = await task_collection.insert_one(taskCollection)
                            return OrganizationResults
                        else:
                            result = getattr(
                                getattr(dashboard, category), operationId)(**parameter)
                            logging.info(result)
                            
                            taskCollection = {"task_name": operationId,
                                                "start_time": dt_string,
                                                "organization": organization,
                                                "usefulParameter": data.usefulParameter,
                                                "category": category,
                                                "method": data.method,
                                                "rollback": data.isRollbackActive,
                                                "parameter": parameter,
                                                "response": result,
                                                "error": False}
                            task = await task_collection.insert_one(taskCollection)
                            return result
                    else:
                        # remove organizationId because already passed in the loop, keep other parameters

                        parameter.pop("organizationId")
                        OrganizationList = data.organizationIDSelected
                        OrganizationResults = []
                        for organizationId in OrganizationList:
                            result = getattr(getattr(dashboard, category), operationId)(
                                organizationId, **parameter)
                            loop_parameter.append(
                                {"organizationId": organizationId, **parameter})
                            logging.info(result)
                            OrganizationResults.append(result)
                            
                        taskCollection = {
                            "task_name": operationId,
                            "start_time": dt_string,
                            "organization": organization,
                            "usefulParameter": data.usefulParameter,
                            "category": category,
                            "method": data.method,
                            "rollback": data.isRollbackActive,
                            "parameter": loop_parameter,

                            "response": OrganizationResults,
                            "rollback_response": RollbackResponse,
                            "error": False
                        }
                        task = await task_collection.insert_one(taskCollection)

                        return OrganizationResults

                except (meraki.APIError, TypeError,KeyError, AttributeError) as err:
                    if TypeError:
                        logging.error(err.args)
                        
                        taskCollection = {
                            "task_name": operationId,
                            "start_time": dt_string,
                            "organization": organization,
                            "usefulParameter": data.usefulParameter,
                            "category": category,
                            "method": data.method,
                            "rollback": data.isRollbackActive,
                            "parameter": loop_parameter,

                            "response": err.args,
                            "rollback_response": RollbackResponse,
                            "error": True
                        }
                        task = await task_collection.insert_one(taskCollection)
                        return {"error": err.args}
                    if KeyError:
                        logging.error(err)
                        print(err)
                        
                        taskCollection = {
                            "task_name": operationId,
                            "start_time": dt_string,
                            "organization": organization,
                            "usefulParameter": data.usefulParameter,
                            "category": category,
                            "method": data.method,
                            "rollback": data.isRollbackActive,
                            "parameter": loop_parameter,

                            "response": err,
                            "rollback_response": RollbackResponse,
                            "error": True
                        }
                        task = await task_collection.insert_one(taskCollection)
                        return {"error": err}
                    if AttributeError:
                        logging.error(err)
                        print(err)
                        
                        taskCollection = {
                            "task_name": operationId,
                            "start_time": dt_string,
                            "organization": organization,
                            "usefulParameter": data.usefulParameter,
                            "category": category,
                            "method": data.method,
                            "rollback": data.isRollbackActive,
                            "parameter": loop_parameter,

                            "response": err,
                            "rollback_response": RollbackResponse,
                            "error": True
                        }
                        task = await task_collection.insert_one(taskCollection)
                        return {"error": err}
                    else:
                        logging.error(err.status)
                        logging.error(err.reason)
                        logging.error(err.message)
                        taskCollection = {
                            "task_name": operationId,
                            "start_time": dt_string,
                            "organization": organization,
                            "usefulParameter": data.usefulParameter,
                            "category": category,
                            "method": data.method,
                            "rollback": data.isRollbackActive,
                            "parameter": loop_parameter,

                            "response": err.reason,
                            "rollback_response": RollbackResponse,
                            "error": True
                        }
                        task = await task_collection.insert_one(taskCollection)
                        

                    
                    return {'status': err.status, "message": err.message, "error": err.reason}
            elif data.isRollbackActive == False:
                try:
                    logging.info(f"{dt_string} NEW API CALL")
                    API_KEY = data.apiKey
                    dashboard = meraki.DashboardAPI(
                        API_KEY, output_log=False, suppress_logging=False)

                    category = data.responsePrefixes["category"]
                    operationId = data.responsePrefixes["operationId"]
                    parameter = data.ParameterTemplate
                    loop_parameter = []

                    # Special Exception for getOrganizations
                    if data.responsePrefixes["operationId"] == "getOrganizations":
                        result = getattr(
                            getattr(dashboard, category), operationId)()
                        logging.info(result)
                        
                        taskCollection = {"task_name": operationId,
                                            "start_time": dt_string,
                                            "organization": organization,
                                            "usefulParameter": data.usefulParameter,
                                            "category": category,
                                            "method": data.method,
                                            "rollback": data.isRollbackActive,
                                            "parameter": parameter,
                                            "response": result,
                                            "error": False}
                        task = await task_collection.insert_one(taskCollection)
                        return result

                    if len(data.organizationIDSelected) == 0:
                        if "," in parameter["organizationId"]:
                            # remove all whitespace characters (space, tab, newline, and so on)
                            noSpaces = ''.join(
                                parameter["organizationId"].split())
                            # split in array by comma
                            organizationIdArray = noSpaces.split(",")
                            # remove organizationId because already passed in the organizationIdArray, keep other parameters
                            parameter.pop("organizationId")
                            OrganizationResults = []
                            for organizationId in organizationIdArray:
                                result = getattr(getattr(dashboard, category), operationId)(
                                    organizationId, **parameter)
                                loop_parameter.append(
                                    {"organizationId": organizationId, **parameter})
                                logging.info(result)
                                OrganizationResults.append(result)
                                
                            taskCollection = {"task_name": operationId,
                                                "start_time": dt_string,
                                                "organization": organization,
                                                "usefulParameter": data.usefulParameter,
                                                "category": category,
                                                "method": data.method,
                                                "rollback": data.isRollbackActive,
                                                "parameter": loop_parameter,
                                                "response": OrganizationResults,
                                                "error": False}
                            task = await task_collection.insert_one(taskCollection)
                            logging.info(OrganizationResults)
                            return OrganizationResults
                        else:
                            result = getattr(
                                getattr(dashboard, category), operationId)(**parameter)
                            logging.info(result)
                            
                            taskCollection = {"task_name": operationId,
                                                "start_time": dt_string,
                                                "organization": organization,
                                                "usefulParameter": data.usefulParameter,
                                                "category": category,
                                                "method": data.method,
                                                "rollback": data.isRollbackActive,
                                                "parameter": parameter,
                                                "response": result,
                                                "error": False}
                            task = await task_collection.insert_one(taskCollection)
                            return result

                    else:
                        # remove organizationId because already passed in the loop, keep other parameters
                        parameter.pop("organizationId")
                        OrganizationList = data.organizationIDSelected
                        OrganizationResults = []

                        for organizationId in OrganizationList:
                            result = getattr(getattr(dashboard, category), operationId)(
                                organizationId, **parameter)
                            loop_parameter.append(
                                {"organizationId": organizationId, **parameter})
                            logging.info(result)
                            OrganizationResults.append(result)
                            

                        taskCollection = {"task_name": operationId,
                                            "start_time": dt_string,
                                            "organization": organization,
                                            "usefulParameter": data.usefulParameter,
                                            "category": category,
                                            "method": data.method,
                                            "rollback": data.isRollbackActive,
                                            "parameter": loop_parameter,

                                            "response": OrganizationResults,
                                            "error": False}
                        task = await task_collection.insert_one(taskCollection)

                        return OrganizationResults

                except (meraki.APIError, TypeError,KeyError, AttributeError) as err:
                    if TypeError:
                        logging.error(err.args)
                        
                        taskCollection = {"task_name": operationId,
                                            "start_time": dt_string,
                                            "organization": organization,
                                            "usefulParameter": data.usefulParameter,
                                            "category": category,
                                            "method": data.method,
                                            "rollback": data.isRollbackActive,
                                            "parameter": loop_parameter,

                                            "response": err.args,
                                            "error": True}
                        task = await task_collection.insert_one(taskCollection)
                        return {"error": err.args}
                    if KeyError:
                        logging.error(err)
                        
                        taskCollection = {"task_name": operationId,
                                            "start_time": dt_string,
                                            "organization": organization,
                                            "usefulParameter": data.usefulParameter,
                                            "category": category,
                                            "method": data.method,
                                            "rollback": data.isRollbackActive,
                                            "parameter": loop_parameter,

                                            "response": err,
                                            "error": True}
                        task = await task_collection.insert_one(taskCollection)
                        return {"error": err}
                    if AttributeError:
                        logging.error(err)
                        
                        taskCollection = {"task_name": operationId,
                                            "start_time": dt_string,
                                            "organization": organization,
                                            "usefulParameter": data.usefulParameter,
                                            "category": category,
                                            "method": data.method,
                                            "rollback": data.isRollbackActive,
                                            "parameter": loop_parameter,

                                            "response": err,
                                            "error": True}
                        task = await task_collection.insert_one(taskCollection)
                        return {"error": err}
                    else:
                        logging.error(err.status)
                        logging.error(err.reason)
                        logging.error(err.message)
                        taskCollection = {"task_name": operationId,
                                            "start_time": dt_string,
                                            "organization": organization,
                                            "usefulParameter": data.usefulParameter,
                                            "category": category,
                                            "method": data.method,
                                            "rollback": data.isRollbackActive,
                                            "parameter": loop_parameter,

                                            "response": err.reason,
                                            "error": True}
                        task = await task_collection.insert_one(taskCollection)
                        

                    
                    return {'status': err.status, "message": err.message, "error": err.reason}
    elif data.useJsonBody == True:
        if data.usefulParameter == "networkId":
            if data.isRollbackActive == True:
                try:
                    logging.info(f"{dt_string} NEW API CALL")
                    API_KEY = data.apiKey
                    dashboard = meraki.DashboardAPI(
                        API_KEY, output_log=False, suppress_logging=False)

                    category = data.responsePrefixes["category"]
                    operationId = data.responsePrefixes["operationId"]
                    parameter = data.ParameterTemplate
                    requiredParameters = data.requiredParameters
                    rollbackId = data.responsePrefixes["rollbackId"]
                    RollbackResponse = []

                    # get only required parameter in get-rollbackId
                    rollbackGetparameters = dict()
                    for (key, value) in parameter.items():
                        if key in requiredParameters:
                            rollbackGetparameters[key] = value

                    if len(data.networksIDSelected) == 0:
                        if "," in parameter["networkId"]:
                            # remove all whitespace characters (space, tab, newline, and so on)
                            noSpaces = ''.join(
                                parameter["networkId"].split())
                            # split in array by comma
                            networkIdArray = noSpaces.split(",")

                            for index, networkId in enumerate(networkIdArray):
                                result = getattr(
                                    getattr(dashboard, category), rollbackId)(**rollbackGetparameters)
                                logging.info(result)
                                RollbackResponse.append(result)
                                RollbackResponse[index]["networkId"] = networkId
                                
                            logging.info(RollbackResponse)
                        else:
                            networkId = parameter["networkId"]
                            RollbackResponse = getattr(
                                getattr(dashboard, category), rollbackId)(**rollbackGetparameters)
                            RollbackResponse["networkId"] = networkId
                            
                            logging.info(RollbackResponse)

                    else:
                        NetworkList = data.networksIDSelected
                        NetworkResults = []

                        for index, networkId in enumerate(NetworkList):
                            result = getattr(
                                getattr(dashboard, category), rollbackId)(**rollbackGetparameters)
                            RollbackResponse.append(result)
                            RollbackResponse[index]["networkId"] = networkId
                            logging.info(result)

                except (meraki.APIError, TypeError,KeyError) as err:
                    if TypeError:
                        logging.error(err.args)
                        
                        taskCollection = {
                            "task_name": rollbackId,
                            "start_time": dt_string,
                            "organization": organization,
                            "usefulParameter": data.usefulParameter,
                            "category": category,
                            "method": data.method,
                            "rollback": data.isRollbackActive,
                            "parameter": "",

                            "response": err.args,
                            "rollback_response": RollbackResponse,
                            "error": True
                        }
                        task = await task_collection.insert_one(taskCollection)
                        return {"error": err.args}
                    if KeyError:
                        logging.error(err)
                        
                        taskCollection = {
                            "task_name": rollbackId,
                            "start_time": dt_string,
                            "organization": organization,
                            "usefulParameter": data.usefulParameter,
                            "category": category,
                            "method": data.method,
                            "rollback": data.isRollbackActive,
                            "parameter": "",

                            "response": err,
                            "rollback_response": RollbackResponse,
                            "error": True
                        }
                        task = await task_collection.insert_one(taskCollection)
                        return {"error": err}
                    else:
                        logging.error(err.status)
                        logging.error(err.reason)
                        logging.error(err.message)
                        taskCollection = {
                            "task_name": rollbackId,
                            "start_time": dt_string,
                            "organization": organization,
                            "usefulParameter": data.usefulParameter,
                            "category": category,
                            "method": data.method,
                            "rollback": data.isRollbackActive,
                            "parameter": "",

                            "response": err.reason,
                            "rollback_response": RollbackResponse,
                            "error": True
                        }
                        task = await task_collection.insert_one(taskCollection)
                        

                    
                    return {'status': err.status, "message": err.message, "error": err.reason}
                try:
                    logging.info(f"{dt_string} NEW API CALL")
                    API_KEY = data.apiKey
                    dashboard = meraki.DashboardAPI(
                        API_KEY, output_log=False, suppress_logging=False)

                    category = data.responsePrefixes["category"]
                    operationId = data.responsePrefixes["operationId"]
                    parameter = data.ParameterTemplate
                    loop_parameter = []

                    if len(data.networksIDSelected) == 0:
                        JsonBodyparameter = data.ParameterTemplateJSON
                        if "," in parameter["networkId"]:
                            # remove all whitespace characters (space, tab, newline, and so on)
                            noSpaces = ''.join(
                                parameter["networkId"].split())
                            # split in array by comma
                            networkIdArray = noSpaces.split(",")
                            # remove networkId because already passed in the networkIdArray, keep other parameters
                            parameter.pop("networkId")
                            NetworkResults = []
                            for networkId in networkIdArray:
                                result = getattr(getattr(dashboard, category), operationId)(
                                    networkId, **JsonBodyparameter)
                                loop_parameter.append(
                                    {"networkId": networkId, **parameter})
                                logging.info(result)
                                NetworkResults.append(result)
                                
                            taskCollection = {"task_name": operationId,
                                                "start_time": dt_string,
                                                "organization": organization,
                                                "usefulParameter": data.usefulParameter,
                                                "category": category,
                                                "method": data.method,
                                                "rollback": data.isRollbackActive,
                                                "parameter": loop_parameter,
                                                "response": NetworkResults,
                                                "error": False}
                            task = await task_collection.insert_one(taskCollection)
                            return NetworkResults

                        else:
                            JsonBodyparameter = data.ParameterTemplateJSON
                            mixedParameters = {
                                **parameter, **JsonBodyparameter}
                            result = getattr(
                                getattr(dashboard, category), operationId)(**mixedParameters)
                            logging.info(result)
                            
                            taskCollection = {"task_name": operationId,
                                                "start_time": dt_string,
                                                "organization": organization,
                                                "usefulParameter": data.usefulParameter,
                                                "category": category,
                                                "method": data.method,
                                                "rollback": data.isRollbackActive,
                                                "parameter": parameter,
                                                "response": result,
                                                "error": False}
                            task = await task_collection.insert_one(taskCollection)
                            return result

                    else:
                        JsonBodyparameter = data.ParameterTemplateJSON
                        mixedParameters = {
                            **parameter, **JsonBodyparameter}
                        # remove serial because already passed in the loop, keep other parameters
                        mixedParameters.pop("networkId")

                        NetworkList = data.networksIDSelected
                        NetworkResults = []

                        for networkId in NetworkList:

                            result = getattr(getattr(dashboard, category), operationId)(
                                networkId, **mixedParameters)
                            loop_parameter.append(
                                {"networkId": networkId, **mixedParameters})
                            logging.info(result)
                            NetworkResults.append(result)
                            
                        taskCollection = {
                            "task_name": operationId,
                            "start_time": dt_string,
                            "organization": organization,
                            "usefulParameter": data.usefulParameter,
                            "category": category,
                            "method": data.method,
                            "rollback": data.isRollbackActive,
                            "parameter": loop_parameter,

                            "response": NetworkResults,
                            "rollback_response": RollbackResponse,
                            "error": False
                        }
                        task = await task_collection.insert_one(taskCollection)
                        return NetworkResults

                except (meraki.APIError, TypeError,KeyError) as err:
                    if TypeError:
                        logging.error(err.args)
                        
                        taskCollection = {
                            "task_name": operationId,
                            "start_time": dt_string,
                            "organization": organization,
                            "usefulParameter": data.usefulParameter,
                            "category": category,
                            "method": data.method,
                            "rollback": data.isRollbackActive,
                            "parameter": loop_parameter,

                            "response": err.args,
                            "rollback_response": RollbackResponse,
                            "error": True
                        }
                        task = await task_collection.insert_one(taskCollection)
                        return {"error": err.args}
                    if KeyError:
                        logging.error(err)
                        
                        taskCollection = {
                            "task_name": operationId,
                            "start_time": dt_string,
                            "organization": organization,
                            "usefulParameter": data.usefulParameter,
                            "category": category,
                            "method": data.method,
                            "rollback": data.isRollbackActive,
                            "parameter": loop_parameter,

                            "response": err,
                            "rollback_response": RollbackResponse,
                            "error": True
                        }
                        task = await task_collection.insert_one(taskCollection)
                        return {"error": err}
                    else:
                        logging.error(err.status)
                        logging.error(err.reason)
                        logging.error(err.message)
                        taskCollection = {
                            "task_name": operationId,
                            "start_time": dt_string,
                            "organization": organization,
                            "usefulParameter": data.usefulParameter,
                            "category": category,
                            "method": data.method,
                            "rollback": data.isRollbackActive,
                            "parameter": loop_parameter,

                            "response": err.reason,
                            "rollback_response": RollbackResponse,
                            "error": True
                        }
                        task = await task_collection.insert_one(taskCollection)
                        

                    
                    return {'status': err.status, "message": err.message, "error": err.reason}
            elif data.isRollbackActive == False:
                try:
                    logging.info(f"{dt_string} NEW API CALL")
                    API_KEY = data.apiKey
                    dashboard = meraki.DashboardAPI(
                        API_KEY, output_log=False, suppress_logging=False)

                    category = data.responsePrefixes["category"]
                    operationId = data.responsePrefixes["operationId"]
                    parameter = data.ParameterTemplate
                    loop_parameter = []

                    if len(data.networksIDSelected) == 0:
                        JsonBodyparameter = data.ParameterTemplateJSON
                        if "," in parameter["networkId"]:
                            # remove all whitespace characters (space, tab, newline, and so on)
                            noSpaces = ''.join(
                                parameter["networkId"].split())
                            # split in array by comma
                            networkIdArray = noSpaces.split(",")
                            # remove networkId because already passed in the networkIdArray, keep other parameters
                            parameter.pop("networkId")
                            DeviceResults = []
                            for networkId in networkIdArray:
                                result = getattr(getattr(dashboard, category), operationId)(
                                    networkId, **JsonBodyparameter)
                                loop_parameter.append(
                                    {"networkId": networkId, **parameter})
                                logging.info(result)
                                DeviceResults.append(result)
                                
                            taskCollection = {"task_name": operationId,
                                                "start_time": dt_string,
                                                "organization": organization,
                                                "usefulParameter": data.usefulParameter,
                                                "category": category,
                                                "method": data.method,
                                                "rollback": data.isRollbackActive,
                                                "parameter": loop_parameter,
                                                "response": DeviceResults,
                                                "error": False}
                            task = await task_collection.insert_one(taskCollection)
                            return DeviceResults

                        else:
                            JsonBodyparameter = data.ParameterTemplateJSON
                            mixedParameters = {
                                **parameter, **JsonBodyparameter}
                            result = getattr(
                                getattr(dashboard, category), operationId)(**mixedParameters)
                            logging.info(result)
                            
                            taskCollection = {"task_name": operationId,
                                                "start_time": dt_string,
                                                "organization": organization,
                                                "usefulParameter": data.usefulParameter,
                                                "category": category,
                                                "method": data.method,
                                                "rollback": data.isRollbackActive,
                                                "parameter": parameter,
                                                "response": result,
                                                "error": False}
                            task = await task_collection.insert_one(taskCollection)
                            return result

                    else:
                        JsonBodyparameter = data.ParameterTemplateJSON
                        mixedParameters = {
                            **parameter, **JsonBodyparameter}
                        # remove networkId because already passed in the loop, keep other parameters
                        mixedParameters.pop("networkId")

                        NetworkList = data.networksIDSelected
                        NetworkResults = []

                        for networkId in NetworkList:

                            result = getattr(getattr(dashboard, category), operationId)(
                                networkId, **mixedParameters)
                            loop_parameter.append(
                                {"networkId": networkId, **mixedParameters})
                            logging.info(result)

                            NetworkResults.append(result)
                            
                        taskCollection = {"task_name": operationId,
                                            "start_time": dt_string,
                                            "organization": organization,
                                            "usefulParameter": data.usefulParameter,
                                            "category": category,
                                            "method": data.method,
                                            "rollback": data.isRollbackActive,
                                            "parameter": loop_parameter,

                                            "response": NetworkResults,
                                            "error": False}
                        task = await task_collection.insert_one(taskCollection)
                        return NetworkResults

                except (meraki.APIError, TypeError,KeyError) as err:
                    if TypeError:
                        logging.error(err.args)
                        
                        taskCollection = {"task_name": operationId,
                                            "start_time": dt_string,
                                            "organization": organization,
                                            "usefulParameter": data.usefulParameter,
                                            "category": category,
                                            "method": data.method,
                                            "rollback": data.isRollbackActive,
                                            "parameter": loop_parameter,

                                            "response": err.args,
                                            "error": True}
                        task = await task_collection.insert_one(taskCollection)
                        return {"error": err.args}
                    if KeyError:
                        logging.error(err)
                        
                        taskCollection = {"task_name": operationId,
                                            "start_time": dt_string,
                                            "organization": organization,
                                            "usefulParameter": data.usefulParameter,
                                            "category": category,
                                            "method": data.method,
                                            "rollback": data.isRollbackActive,
                                            "parameter": loop_parameter,

                                            "response": err,
                                            "error": True}
                        task = await task_collection.insert_one(taskCollection)
                        return {"error": err}
                    else:
                        logging.error(err.status)
                        logging.error(err.reason)
                        logging.error(err.message)
                        taskCollection = {"task_name": operationId,
                                            "start_time": dt_string,
                                            "organization": organization,
                                            "usefulParameter": data.usefulParameter,
                                            "category": category,
                                            "method": data.method,
                                            "rollback": data.isRollbackActive,
                                            "parameter": loop_parameter,

                                            "response": err.reason,
                                            "error": True}
                        task = await task_collection.insert_one(taskCollection)
                        

                    
                    return {'status': err.status, "message": err.message, "error": err.reason}

        elif data.usefulParameter == "serial":
            if data.isRollbackActive == True:
                try:
                    logging.info(f"{dt_string} NEW API CALL")
                    API_KEY = data.apiKey
                    dashboard = meraki.DashboardAPI(
                        API_KEY, output_log=False, suppress_logging=False,retry_4xx_error=True,retry_4xx_error_wait_time=3,maximum_retries=2)

                    category = data.responsePrefixes["category"]
                    parameter = data.ParameterTemplate
                    rollbackId = data.responsePrefixes["rollbackId"]
                    requiredParameters = data.requiredParameters
                    RollbackResponse = []

                    # get only required parameter in get-rollbackId
                    rollbackGetparameters = dict()
                    for (key, value) in parameter.items():
                        if key in requiredParameters:
                            rollbackGetparameters[key] = value

                    if len(data.devicesIDSelected) == 0:
                        if "," in parameter["serial"]:
                            # remove all whitespace characters (space, tab, newline, and so on)
                            noSpaces = ''.join(parameter["serial"].split())
                            # split in array by comma
                            serialArray = noSpaces.split(",")

                            for index, serial in enumerate(serialArray):
                                try:
                                    
                                    result = getattr(
                                        getattr(dashboard, category), rollbackId)(**rollbackGetparameters)
                                    logging.info(result)
                                    RollbackResponse.append(result)
                                    RollbackResponse[index]["serial"] = serial
                                except (meraki.APIError,TypeError, KeyError, meraki.APIKeyError, ValueError) as err:
                                    RollbackResponse.append({"error": {"serial" : serial,"msg": str(err), "status": err.status}})
                                    if err.status == 401 | 404 | 403:
                                        logging.error({"error": {"serial" : serial,"msg": str(err), "status": err.status}})
                                        continue
                                
                            logging.info(RollbackResponse)
                        else:
                            try:
                                serial = parameter["serial"]
                                RollbackResponse = getattr(
                                    getattr(dashboard, category), rollbackId)(**rollbackGetparameters)
                                RollbackResponse["serial"] = serial
                            except (meraki.APIError,TypeError, KeyError, meraki.APIKeyError, ValueError) as err:
                                RollbackResponse = ({"error": {"serial" : serial,"msg": str(err), "status": err.status}})
                                if err.status == 401 | 404 | 403:
                                    logging.error({"error": {"serial" : serial,"msg": str(err), "status": err.status}})
                                    
                                    
                            
                    else:
                        DevicesList = data.devicesIDSelected

                        for index, serial in enumerate(DevicesList):
                            try:
                                result = getattr(
                                    getattr(dashboard, category), rollbackId)(**rollbackGetparameters)
                                logging.info(result)
                                RollbackResponse.append(result)
                                RollbackResponse[index]["serial"] = serial
                            except (meraki.APIError,TypeError, KeyError, meraki.APIKeyError, ValueError) as err:
                                RollbackResponse.append({"error": {"serial" : serial,"msg": str(err), "status": err.status}})
                                if err.status == 401 | 404 | 403:
                                    logging.error({"error": {"serial" : serial,"msg": str(err), "status": err.status}})
                                    continue
                            
                        logging.info(RollbackResponse)

                except (meraki.APIError, TypeError,KeyError) as err:
                    if TypeError:
                        logging.error(err.args)
                        
                        taskCollection = {
                            "task_name": rollbackId,
                            "start_time": dt_string,
                            "organization": organization,
                            "usefulParameter": data.usefulParameter,
                            "category": category,
                            "method": data.method,
                            "rollback": data.isRollbackActive,
                            "parameter": "",

                            "response": err.args,
                            "rollback_response": RollbackResponse,
                            "error": True
                        }
                        task = await task_collection.insert_one(taskCollection)
                        return {"error": err.args}
                    if KeyError:
                        logging.error(err)
                        
                        taskCollection = {
                            "task_name": rollbackId,
                            "start_time": dt_string,
                            "organization": organization,
                            "usefulParameter": data.usefulParameter,
                            "category": category,
                            "method": data.method,
                            "rollback": data.isRollbackActive,
                            "parameter": "",

                            "response": err,
                            "rollback_response": RollbackResponse,
                            "error": True
                        }
                        task = await task_collection.insert_one(taskCollection)
                        return {"error": err}
                    else:
                        logging.error(err.status)
                        logging.error(err.reason)
                        logging.error(err.message)
                        taskCollection = {
                            "task_name": rollbackId,
                            "start_time": dt_string,
                            "organization": organization,
                            "usefulParameter": data.usefulParameter,
                            "category": category,
                            "method": data.method,
                            "rollback": data.isRollbackActive,
                            "parameter": "",

                            "response": err.reason,
                            "rollback_response": RollbackResponse,
                            "error": True
                        }
                        task = await task_collection.insert_one(taskCollection)
                        

                    
                    return {'status': err.status, "message": err.message, "error": err.reason}
                try:
                    logging.info(f"{dt_string} NEW API CALL")
                    API_KEY = data.apiKey
                    dashboard = meraki.DashboardAPI(
                        API_KEY, output_log=False, suppress_logging=False)

                    category = data.responsePrefixes["category"]
                    operationId = data.responsePrefixes["operationId"]
                    parameter = data.ParameterTemplate
                    loop_parameter = []

                    if len(data.devicesIDSelected) == 0:
                        JsonBodyparameter = data.ParameterTemplateJSON
                        if "," in parameter["serial"]:
                            # remove all whitespace characters (space, tab, newline, and so on)
                            noSpaces = ''.join(parameter["serial"].split())
                            # split in array by comma
                            serialArray = noSpaces.split(",")
                            # remove serial because already passed in the serialArray, keep other parameters
                            parameter.pop("serial")
                            DeviceResults = []
                            for serial in serialArray:
                                try:
                                    result = getattr(getattr(dashboard, category), operationId)(
                                        serial, **JsonBodyparameter)
                                    loop_parameter.append(
                                        {"serial": serial, **parameter})
                                    logging.info(result)
                                    DeviceResults.append(result)
                                except (meraki.APIError,TypeError, KeyError, meraki.APIKeyError, ValueError) as err:
                                    DeviceResults.append({"error": {"serial" : serial,"msg": str(err), "status": err.status}})
                                    if err.status == 401 | 404 | 403:
                                        logging.error({"error": {"serial" : serial,"msg": str(err), "status": err.status}})
                                        continue
                                
                            taskCollection = {"task_name": operationId,
                                                "start_time": dt_string,
                                                "organization": organization,
                                                "usefulParameter": data.usefulParameter,
                                                "category": category,
                                                "method": data.method,
                                                "rollback": data.isRollbackActive,
                                                "parameter": loop_parameter,
                                                "response": DeviceResults,
                                                "error": False}
                            task = await task_collection.insert_one(taskCollection)
                            return DeviceResults
                        else:
                            try:
                                JsonBodyparameter = data.ParameterTemplateJSON
                                mixedParameters = {
                                    **parameter, **JsonBodyparameter}
                                result = getattr(
                                    getattr(dashboard, category), operationId)(**mixedParameters)
                                logging.info(result)
                                
                                taskCollection = {"task_name": operationId,
                                                    "start_time": dt_string,
                                                    "organization": organization,
                                                    "usefulParameter": data.usefulParameter,
                                                    "category": category,
                                                    "method": data.method,
                                                    "rollback": data.isRollbackActive,
                                                    "parameter": parameter,
                                                    "response": result,
                                                    "error": False}
                                task = await task_collection.insert_one(taskCollection)
                                return result

                            except (meraki.APIError,TypeError, KeyError, meraki.APIKeyError, ValueError) as err:
                                if err.status == 401 | 404 | 403:
                                    result = {"error": {"serial" : parameter["serial"],"msg": str(err), "status": err.status}}
                                    logging.error(result)
                                return {"error": {"serial" : parameter["serial"],"msg": str(err), "status": err.status}}
                                    
                                
                    else:
                        JsonBodyparameter = data.ParameterTemplateJSON
                        mixedParameters = {
                            **parameter, **JsonBodyparameter}
                        # remove serial because already passed in the loop, keep other parameters
                        if "serial" in mixedParameters:
                            mixedParameters.pop("serial")

                        DevicesList = data.devicesIDSelected
                        DeviceResults = []

                        for serial in DevicesList:
                            try:
                                result = getattr(getattr(dashboard, category), operationId)(
                                    serial, **mixedParameters)
                                loop_parameter.append(
                                    {"serial": serial, **mixedParameters})
                                logging.info(result)
                                DeviceResults.append(result)
                            except (meraki.APIError,TypeError, KeyError, meraki.APIKeyError, ValueError) as err:
                                DeviceResults.append({"error": {"serial" : serial,"msg": str(err), "status": err.status}})
                                if err.status == 401 | 404 | 403:
                                    logging.error({"error": {"serial" : serial,"msg": str(err), "status": err.status}})
                                    continue
                            
                        taskCollection = {
                            "task_name": operationId,
                            "start_time": dt_string,
                            "organization": organization,
                            "usefulParameter": data.usefulParameter,
                            "category": category,
                            "method": data.method,
                            "rollback": data.isRollbackActive,
                            "parameter": loop_parameter,

                            "response": DeviceResults,
                            "rollback_response": RollbackResponse,
                            "error": False
                        }
                        task = await task_collection.insert_one(taskCollection)
                        return DeviceResults

                except (meraki.APIError, TypeError,KeyError) as err:
                    if TypeError:
                        logging.error(err.args)
                        
                        taskCollection = {
                            "task_name": operationId,
                            "start_time": dt_string,
                            "organization": organization,
                            "usefulParameter": data.usefulParameter,
                            "category": category,
                            "method": data.method,
                            "rollback": data.isRollbackActive,
                            "parameter": loop_parameter,

                            "response": err.args,
                            "rollback_response": RollbackResponse,
                            "error": True
                        }
                        task = await task_collection.insert_one(taskCollection)
                        return {"error": err.args}
                    if KeyError:
                        logging.error(err)
                        
                        taskCollection = {
                            "task_name": operationId,
                            "start_time": dt_string,
                            "organization": organization,
                            "usefulParameter": data.usefulParameter,
                            "category": category,
                            "method": data.method,
                            "rollback": data.isRollbackActive,
                            "parameter": loop_parameter,

                            "response": err,
                            "rollback_response": RollbackResponse,
                            "error": True
                        }
                        task = await task_collection.insert_one(taskCollection)
                        return {"error": err}
                    else:
                        logging.error(err.status)
                        logging.error(err.reason)
                        logging.error(err.message)
                        
                        taskCollection = {
                            "task_name": operationId,
                            "start_time": dt_string,
                            "organization": organization,
                            "usefulParameter": data.usefulParameter,
                            "category": category,
                            "method": data.method,
                            "rollback": data.isRollbackActive,
                            "parameter": loop_parameter,

                            "response": err.reason,
                            "rollback_response": RollbackResponse,
                            "error": True
                        }
                        task = await task_collection.insert_one(taskCollection)

                    
                    return {'status': err.status, "message": err.message, "error": err.reason}
            elif data.isRollbackActive == False:
                try:
                    logging.info(f"{dt_string} NEW API CALL")
                    API_KEY = data.apiKey
                    dashboard = meraki.DashboardAPI(
                        API_KEY, output_log=False, suppress_logging=False,retry_4xx_error=True,retry_4xx_error_wait_time=3,maximum_retries=2)

                    category = data.responsePrefixes["category"]
                    operationId = data.responsePrefixes["operationId"]
                    parameter = data.ParameterTemplate
                    loop_parameter = []

                    if len(data.devicesIDSelected) == 0:
                        JsonBodyparameter = data.ParameterTemplateJSON
                        if "," in parameter["serial"]:
                            # remove all whitespace characters (space, tab, newline, and so on)
                            noSpaces = ''.join(parameter["serial"].split())
                            # split in array by comma
                            serialArray = noSpaces.split(",")
                            # remove serial because already passed in the serialArray, keep other parameters
                            parameter.pop("serial")
                            DeviceResults = []
                            for serial in serialArray:
                                try:
                                    result = getattr(getattr(dashboard, category), operationId)(
                                        serial, **JsonBodyparameter)
                                    loop_parameter.append(
                                        {"serial": serial, **parameter})
                                    logging.info(result)
                                    DeviceResults.append(result)
                                except (meraki.APIError,TypeError, KeyError, meraki.APIKeyError, ValueError) as err:
                                    DeviceResults.append({"error": {"serial" : serial,"msg": str(err), "status": err.status}})
                                    if err.status == 401 | 404 | 403:
                                        logging.error({"error": {"serial" : serial,"msg": str(err), "status": err.status}})
                                        continue
                                
                            taskCollection = {"task_name": operationId,
                                                "start_time": dt_string,
                                                "organization": organization,
                                                "usefulParameter": data.usefulParameter,
                                                "category": category,
                                                "method": data.method,
                                                "rollback": data.isRollbackActive,
                                                "parameter": loop_parameter,
                                                "response": DeviceResults,
                                                "error": False}
                            task = await task_collection.insert_one(taskCollection)
                            return DeviceResults

                        else:
                            try:
                                
                                JsonBodyparameter = data.ParameterTemplateJSON
                                mixedParameters = {
                                    **parameter, **JsonBodyparameter}
                                result = getattr(
                                    getattr(dashboard, category), operationId)(**mixedParameters)
                                logging.info(result)
                                
                                taskCollection = {"task_name": operationId,
                                                    "start_time": dt_string,
                                                    "organization": organization,
                                                    "usefulParameter": data.usefulParameter,
                                                    "category": category,
                                                    "method": data.method,
                                                    "rollback": data.isRollbackActive,
                                                    "parameter": parameter,
                                                    "response": result,
                                                    "error": False}
                                task = await task_collection.insert_one(taskCollection)
                                
                                return result
                            except (meraki.APIError,TypeError, KeyError, meraki.APIKeyError, ValueError) as err:
                                if err.status == 401 | 404 | 403:
                                    result = {"error": {"serial" : parameter["serial"],"msg": str(err), "status": err.status}}
                                    logging.error(result)
                                return {"error": {"serial" : parameter["serial"],"msg": str(err), "status": err.status}}

                    else:
                        JsonBodyparameter = data.ParameterTemplateJSON
                        mixedParameters = {
                            **parameter, **JsonBodyparameter}
                        # remove serial because already passed in the loop, keep other parameters
                        mixedParameters.pop("serial")

                        DevicesList = data.devicesIDSelected
                        DeviceResults = []

                        for serial in DevicesList:
                            try:
                                result = getattr(getattr(dashboard, category), operationId)(
                                    serial, **mixedParameters)
                                loop_parameter.append(
                                    {"serial": serial, **mixedParameters})
                                logging.info(result)
                                DeviceResults.append(result)
                            except (meraki.APIError,TypeError, KeyError, meraki.APIKeyError, ValueError) as err:
                                DeviceResults.append({"error": {"serial" : serial,"msg": str(err), "status": err.status}})
                                if err.status == 401 | 404 | 403:
                                    logging.error({"error": {"serial" : serial,"msg": str(err), "status": err.status}})
                                    continue
                            
                        taskCollection = {"task_name": operationId,
                                            "start_time": dt_string,
                                            "organization": organization,
                                            "usefulParameter": data.usefulParameter,
                                            "category": category,
                                            "method": data.method,
                                            "rollback": data.isRollbackActive,
                                            "parameter": loop_parameter,

                                            "response": DeviceResults,
                                            "error": False}
                        task = await task_collection.insert_one(taskCollection)
                        return DeviceResults

                except (meraki.APIError, TypeError,KeyError) as err:
                    if TypeError:
                        logging.error(err.args)
                        
                        taskCollection = {"task_name": operationId,
                                            "start_time": dt_string,
                                            "organization": organization,
                                            "usefulParameter": data.usefulParameter,
                                            "category": category,
                                            "method": data.method,
                                            "rollback": data.isRollbackActive,
                                            "parameter": loop_parameter,

                                            "response": err.args,
                                            "error": True}
                        task = await task_collection.insert_one(taskCollection)
                        return {"error": err.args}
                    if KeyError:
                        logging.error(err)
                        
                        taskCollection = {"task_name": operationId,
                                            "start_time": dt_string,
                                            "organization": organization,
                                            "usefulParameter": data.usefulParameter,
                                            "category": category,
                                            "method": data.method,
                                            "rollback": data.isRollbackActive,
                                            "parameter": loop_parameter,

                                            "response": err,
                                            "error": True}
                        task = await task_collection.insert_one(taskCollection)
                        return {"error": err}
                    else:
                        logging.error(err.status)
                        logging.error(err.reason)
                        logging.error(err.message)
                        taskCollection = {"task_name": operationId,
                                            "start_time": dt_string,
                                            "organization": organization,
                                            "usefulParameter": data.usefulParameter,
                                            "category": category,
                                            "method": data.method,
                                            "rollback": data.isRollbackActive,
                                            "parameter": loop_parameter,

                                            "response": err.reason,
                                            "error": True}
                        task = await task_collection.insert_one(taskCollection)
                        

                    
                    return {'status': err.status, "message": err.message, "error": err.reason}
        if data.usefulParameter == "organizationId":
            if data.isRollbackActive == True:
                try:
                    logging.info(f"{dt_string} NEW API CALL")
                    API_KEY = data.apiKey
                    dashboard = meraki.DashboardAPI(
                        API_KEY, output_log=False, suppress_logging=False)

                    category = data.responsePrefixes["category"]
                    operationId = data.responsePrefixes["operationId"]
                    parameter = data.ParameterTemplate
                    requiredParameters = data.requiredParameters
                    rollbackId = data.responsePrefixes["rollbackId"]
                    RollbackResponse = []

                    # get only required parameter in get-rollbackId
                    rollbackGetparameters = dict()
                    for (key, value) in parameter.items():
                        if key in requiredParameters:
                            rollbackGetparameters[key] = value

                    if len(data.organizationIDSelected) == 0:
                        if "," in parameter["organizationId"]:
                            # remove all whitespace characters (space, tab, newline, and so on)
                            noSpaces = ''.join(
                                parameter["organizationId"].split())
                            # split in array by comma
                            organizationIdArray = noSpaces.split(",")

                            for index, organizationId in enumerate(organizationIdArray):
                                result = getattr(
                                    getattr(dashboard, category), rollbackId)(**rollbackGetparameters)
                                logging.info(result)
                                RollbackResponse.append(result)
                                RollbackResponse[index]["organizationId"] = organizationId
                                
                            logging.info(RollbackResponse)
                        else:
                            organizationId = parameter["organizationId"]
                            RollbackResponse = getattr(
                                getattr(dashboard, category), rollbackId)(**rollbackGetparameters)
                            RollbackResponse["organizationId"] = organizationId
                            
                            logging.info(RollbackResponse)

                    else:
                        OrganizationList = data.organizationIDSelected
                        OrganizationResult = []

                        for index, organizationId in enumerate(OrganizationList):
                            result = getattr(
                                getattr(dashboard, category), rollbackId)(**rollbackGetparameters)
                            RollbackResponse.append(result)
                            RollbackResponse[index]["organizationId"] = organizationId
                            logging.info(result)

                except (meraki.APIError, TypeError,KeyError, AttributeError) as err:
                    if TypeError:
                        logging.error(err.args)
                        
                        taskCollection = {
                            "task_name": rollbackId,
                            "start_time": dt_string,
                            "organization": organization,
                            "usefulParameter": data.usefulParameter,
                            "category": category,
                            "method": data.method,
                            "rollback": data.isRollbackActive,
                            "parameter": "",

                            "response": err.args,
                            "rollback_response": RollbackResponse,
                            "error": True
                        }
                        task = await task_collection.insert_one(taskCollection)
                        return {"error": err.args}
                    if KeyError:
                        logging.error(err)
                        
                        taskCollection = {
                            "task_name": rollbackId,
                            "start_time": dt_string,
                            "organization": organization,
                            "usefulParameter": data.usefulParameter,
                            "category": category,
                            "method": data.method,
                            "rollback": data.isRollbackActive,
                            "parameter": "",

                            "response": err,
                            "rollback_response": RollbackResponse,
                            "error": True
                        }
                        task = await task_collection.insert_one(taskCollection)
                        return {"error": err}
                    if AttributeError:
                        logging.error(err)
                        
                        taskCollection = {
                            "task_name": rollbackId,
                            "start_time": dt_string,
                            "organization": organization,
                            "usefulParameter": data.usefulParameter,
                            "category": category,
                            "method": data.method,
                            "rollback": data.isRollbackActive,
                            "parameter": "",

                            "response": err,
                            "rollback_response": RollbackResponse,
                            "error": True
                        }
                        task = await task_collection.insert_one(taskCollection)
                        return {"error": err}
                    else:
                        logging.error(err.status)
                        logging.error(err.reason)
                        logging.error(err.message)
                        taskCollection = {
                            "task_name": rollbackId,
                            "start_time": dt_string,
                            "organization": organization,
                            "usefulParameter": data.usefulParameter,
                            "category": category,
                            "method": data.method,
                            "rollback": data.isRollbackActive,
                            "parameter": "",

                            "response": err.reason,
                            "rollback_response": RollbackResponse,
                            "error": True
                        }
                        task = await task_collection.insert_one(taskCollection)
                        

                    
                    return {'status': err.status, "message": err.message, "error": err.reason}
                try:
                    logging.info(f"{dt_string} NEW API CALL")
                    API_KEY = data.apiKey
                    dashboard = meraki.DashboardAPI(
                        API_KEY, output_log=False, suppress_logging=False)

                    category = data.responsePrefixes["category"]
                    operationId = data.responsePrefixes["operationId"]
                    parameter = data.ParameterTemplate
                    loop_parameter = []

                    if len(data.organizationIDSelected) == 0:
                        JsonBodyparameter = data.ParameterTemplateJSON
                        if "," in parameter["organizationId"]:
                            # remove all whitespace characters (space, tab, newline, and so on)
                            noSpaces = ''.join(
                                parameter["organizationId"].split())
                            # split in array by comma
                            organizationIdArray = noSpaces.split(",")
                            # remove organizationId because already passed in the organizationIdArray, keep other parameters
                            parameter.pop("organizationId")
                            OrganizationResult = []
                            for organizationId in organizationIdArray:
                                result = getattr(getattr(dashboard, category), operationId)(
                                    organizationId, **JsonBodyparameter)
                                loop_parameter.append(
                                    {"organizationId": organizationId, **parameter})
                                logging.info(result)
                                OrganizationResult.append(result)
                                
                            taskCollection = {"task_name": operationId,
                                                "start_time": dt_string,
                                                "organization": organization,
                                                "usefulParameter": data.usefulParameter,
                                                "category": category,
                                                "method": data.method,
                                                "rollback": data.isRollbackActive,
                                                "parameter": loop_parameter,
                                                "response": OrganizationResult,
                                                "error": False}
                            task = await task_collection.insert_one(taskCollection)
                            return OrganizationResult

                        else:
                            JsonBodyparameter = data.ParameterTemplateJSON
                            mixedParameters = {
                                **parameter, **JsonBodyparameter}
                            result = getattr(
                                getattr(dashboard, category), operationId)(**mixedParameters)
                            logging.info(result)
                            
                            taskCollection = {"task_name": operationId,
                                                "start_time": dt_string,
                                                "organization": organization,
                                                "usefulParameter": data.usefulParameter,
                                                "category": category,
                                                "method": data.method,
                                                "rollback": data.isRollbackActive,
                                                "parameter": parameter,
                                                "response": result,
                                                "error": False}
                            task = await task_collection.insert_one(taskCollection)
                            return result

                    else:
                        JsonBodyparameter = data.ParameterTemplateJSON
                        mixedParameters = {
                            **parameter, **JsonBodyparameter}
                        # remove serial because already passed in the loop, keep other parameters
                        mixedParameters.pop("organizationId")

                        OrganizationList = data.organizationIDSelected
                        OrganizationResult = []

                        for organizationId in OrganizationList:

                            result = getattr(getattr(dashboard, category), operationId)(
                                organizationId, **mixedParameters)
                            loop_parameter.append(
                                {"organizationId": organizationId, **mixedParameters})
                            logging.info(result)
                            OrganizationResult.append(result)
                            
                        taskCollection = {
                            "task_name": operationId,
                            "start_time": dt_string,
                            "organization": organization,
                            "usefulParameter": data.usefulParameter,
                            "category": category,
                            "method": data.method,
                            "rollback": data.isRollbackActive,
                            "parameter": loop_parameter,

                            "response": OrganizationResult,
                            "rollback_response": RollbackResponse,
                            "error": False
                        }
                        task = await task_collection.insert_one(taskCollection)
                        return OrganizationResult

                except (meraki.APIError, TypeError,KeyError, AttributeError) as err:
                    if TypeError:
                        logging.error(err.args)
                        
                        taskCollection = {
                            "task_name": operationId,
                            "start_time": dt_string,
                            "organization": organization,
                            "usefulParameter": data.usefulParameter,
                            "category": category,
                            "method": data.method,
                            "rollback": data.isRollbackActive,
                            "parameter": loop_parameter,

                            "response": err.args,
                            "rollback_response": RollbackResponse,
                            "error": True
                        }
                        task = await task_collection.insert_one(taskCollection)
                        return {"error": err.args}
                    if KeyError:
                        logging.error(err)
                        
                        taskCollection = {
                            "task_name": operationId,
                            "start_time": dt_string,
                            "organization": organization,
                            "usefulParameter": data.usefulParameter,
                            "category": category,
                            "method": data.method,
                            "rollback": data.isRollbackActive,
                            "parameter": loop_parameter,

                            "response": err,
                            "rollback_response": RollbackResponse,
                            "error": True
                        }
                        task = await task_collection.insert_one(taskCollection)
                        return {"error": err}
                    if AttributeError:
                        logging.error(err)
                        
                        taskCollection = {
                            "task_name": operationId,
                            "start_time": dt_string,
                            "organization": organization,
                            "usefulParameter": data.usefulParameter,
                            "category": category,
                            "method": data.method,
                            "rollback": data.isRollbackActive,
                            "parameter": loop_parameter,

                            "response": err,
                            "rollback_response": RollbackResponse,
                            "error": True
                        }
                        task = await task_collection.insert_one(taskCollection)
                        return {"error": err}
                    else:
                        logging.error(err.status)
                        logging.error(err.reason)
                        logging.error(err.message)
                        taskCollection = {
                            "task_name": operationId,
                            "start_time": dt_string,
                            "organization": organization,
                            "usefulParameter": data.usefulParameter,
                            "category": category,
                            "method": data.method,
                            "rollback": data.isRollbackActive,
                            "parameter": loop_parameter,

                            "response": err.reason,
                            "rollback_response": RollbackResponse,
                            "error": True
                        }
                        task = await task_collection.insert_one(taskCollection)
                        

                    
                    return {'status': err.status, "message": err.message, "error": err.reason}
            elif data.isRollbackActive == False:
                try:
                    logging.info(f"{dt_string} NEW API CALL")
                    API_KEY = data.apiKey
                    dashboard = meraki.DashboardAPI(
                        API_KEY, output_log=False, suppress_logging=False)

                    category = data.responsePrefixes["category"]
                    operationId = data.responsePrefixes["operationId"]
                    parameter = data.ParameterTemplate
                    loop_parameter = []

                    if len(data.organizationIDSelected) == 0:
                        JsonBodyparameter = data.ParameterTemplateJSON
                        if "," in parameter["organizationId"]:
                            # remove all whitespace characters (space, tab, newline, and so on)
                            noSpaces = ''.join(
                                parameter["organizationId"].split())
                            # split in array by comma
                            organizationIdArray = noSpaces.split(",")
                            # remove organizationId because already passed in the organizationIdArray, keep other parameters
                            parameter.pop("organizationId")
                            DeviceResults = []
                            for organizationId in organizationIdArray:
                                result = getattr(getattr(dashboard, category), operationId)(
                                    organizationId, **JsonBodyparameter)
                                loop_parameter.append(
                                    {"organizationId": organizationId, **parameter})
                                logging.info(result)
                                DeviceResults.append(result)
                                
                            taskCollection = {"task_name": operationId,
                                                "start_time": dt_string,
                                                "organization": organization,
                                                "usefulParameter": data.usefulParameter,
                                                "category": category,
                                                "method": data.method,
                                                "rollback": data.isRollbackActive,
                                                "parameter": loop_parameter,
                                                "response": DeviceResults,
                                                "error": False}
                            task = await task_collection.insert_one(taskCollection)
                            return DeviceResults

                        else:
                            JsonBodyparameter = data.ParameterTemplateJSON
                            mixedParameters = {
                                **parameter, **JsonBodyparameter}
                            result = getattr(
                                getattr(dashboard, category), operationId)(**mixedParameters)
                            logging.info(result)
                            
                            taskCollection = {"task_name": operationId,
                                                "start_time": dt_string,
                                                "organization": organization,
                                                "usefulParameter": data.usefulParameter,
                                                "category": category,
                                                "method": data.method,
                                                "rollback": data.isRollbackActive,
                                                "parameter": parameter,
                                                "response": result,
                                                "error": False}
                            task = await task_collection.insert_one(taskCollection)
                            return result

                    else:
                        JsonBodyparameter = data.ParameterTemplateJSON
                        mixedParameters = {
                            **parameter, **JsonBodyparameter}
                        # remove organizationId because already passed in the loop, keep other parameters
                        mixedParameters.pop("organizationId")

                        OrganizationList = data.organizationIDSelected
                        OrganizationResult = []

                        for organizationId in OrganizationList:

                            result = getattr(getattr(dashboard, category), operationId)(
                                organizationId, **mixedParameters)
                            loop_parameter.append(
                                {"organizationId": organizationId, **mixedParameters})
                            logging.info(result)

                            OrganizationResult.append(result)
                            
                        taskCollection = {"task_name": operationId,
                                            "start_time": dt_string,
                                            "organization": organization,
                                            "usefulParameter": data.usefulParameter,
                                            "category": category,
                                            "method": data.method,
                                            "rollback": data.isRollbackActive,
                                            "parameter": loop_parameter,

                                            "response": OrganizationResult,
                                            "error": False}
                        task = await task_collection.insert_one(taskCollection)
                        return OrganizationResult

                except (meraki.APIError, TypeError,KeyError, AttributeError) as err:
                    if TypeError:
                        logging.error(err.args)
                        
                        taskCollection = {"task_name": operationId,
                                            "start_time": dt_string,
                                            "organization": organization,
                                            "usefulParameter": data.usefulParameter,
                                            "category": category,
                                            "method": data.method,
                                            "rollback": data.isRollbackActive,
                                            "parameter": loop_parameter,

                                            "response": err.args,
                                            "error": True}
                        task = await task_collection.insert_one(taskCollection)
                        return {"error": err.args}
                    if KeyError:
                        logging.error(err)
                        
                        taskCollection = {"task_name": operationId,
                                            "start_time": dt_string,
                                            "organization": organization,
                                            "usefulParameter": data.usefulParameter,
                                            "category": category,
                                            "method": data.method,
                                            "rollback": data.isRollbackActive,
                                            "parameter": loop_parameter,

                                            "response": err,
                                            "error": True}
                        task = await task_collection.insert_one(taskCollection)
                        return {"error": err}
                    if AttributeError:
                        logging.error(err)
                        
                        taskCollection = {"task_name": operationId,
                                            "start_time": dt_string,
                                            "organization": organization,
                                            "usefulParameter": data.usefulParameter,
                                            "category": category,
                                            "method": data.method,
                                            "rollback": data.isRollbackActive,
                                            "parameter": loop_parameter,

                                            "response": err,
                                            "error": True}
                        task = await task_collection.insert_one(taskCollection)
                        return {"error": err}
                    else:
                        logging.error(err.status)
                        logging.error(err.reason)
                        logging.error(err.message)
                        taskCollection = {"task_name": operationId,
                                            "start_time": dt_string,
                                            "organization": organization,
                                            "usefulParameter": data.usefulParameter,
                                            "category": category,
                                            "method": data.method,
                                            "rollback": data.isRollbackActive,
                                            "parameter": loop_parameter,

                                            "response": err.reason,
                                            "error": True}
                        task = await task_collection.insert_one(taskCollection)
                        

                    
                    return {'status': err.status, "message": err.message, "error": err.reason}




@ app.post("/getAllTasks", tags=["getAllTasks"])
async def getAllTasks(data: getAllTasksData):
    try:
        cursor = database.task_collection.find({}, {'_id': False})
        cursorList = await cursor.to_list(None)
        allTasks = json.loads(json_util.dumps(cursorList))
        return allTasks
    except Exception as err:
        print('error: ', err)
        logging.error(err)
        return {'error: ', err}


@ app.post("/Rollback", tags=["Rollback"])
async def Rollback(data: RollbackData):
    now = datetime.now()
    
    dt_string = now.strftime("%d-%m-%Y %H:%M:%S")
    organization = data.RollbackParameterTemplate["organization"]
    parameter = data.RollbackParameterTemplate["parameter"]
    if type(parameter) is list:
        try:
            logging.info(f"{dt_string} NEW API CALL")
            API_KEY = data.RollbackParameterTemplate["apiKey"]
            dashboard = meraki.DashboardAPI(
                API_KEY, output_log=False, suppress_logging=False)
            category = data.RollbackParameterTemplate["category"]
            operationId = data.RollbackParameterTemplate["operationId"]
            rollbackId = operationId.replace("update", "get")
            usefulParameter = data.RollbackParameterTemplate["usefulParameter"]
            requiredParameters = data.RollbackParameterTemplate["requiredParameters"]
            Rollback_BackResponse = []

            for index, item in enumerate(parameter):
                # get only required parameter in get-rollbackId
                rollbackGetparameters = dict()
                for (key, value) in item.items():
                    if key in requiredParameters:
                        rollbackGetparameters[key] = value

                if usefulParameter == "networkId":
                    networkId = item["networkId"]
                    RollbackResponse = getattr(
                        getattr(dashboard, category), rollbackId)(**rollbackGetparameters)
                    Rollback_BackResponse.append(RollbackResponse)
                    Rollback_BackResponse[index]["networkId"] = networkId
                elif usefulParameter == "serial":
                    serial = item["serial"]
                    RollbackResponse = getattr(
                        getattr(dashboard, category), rollbackId)(**rollbackGetparameters)
                    Rollback_BackResponse.append(RollbackResponse)
                    Rollback_BackResponse[index]["serial"] = serial
                elif usefulParameter == "organizationId":
                    organizationId = item["organizationId"]
                    RollbackResponse = getattr(
                        getattr(dashboard, category), rollbackId)(**rollbackGetparameters)
                    Rollback_BackResponse.append(RollbackResponse)
                    Rollback_BackResponse[index]["organizationId"] = organizationId
                else:
                    RollbackResponse = getattr(
                        getattr(dashboard, category), rollbackId)(**rollbackGetparameters)

                logging.info(Rollback_BackResponse)
                

        except (meraki.APIError, TypeError,KeyError) as err:
            if TypeError:

                logging.error(err.args)
                
                taskCollection = {"task_name": operationId,
                                    "start_time": dt_string,
                                    "organization": organization,
                                    "usefulParameter": usefulParameter,
                                    "category": category,
                                    "method": data.RollbackParameterTemplate["method"],
                                    "rollback": True,
                                    "parameter": parameter,

                                    "response": err.args,
                                    "rollback_response": Rollback_BackResponse,
                                    "error": True
                                    }
                task = await task_collection.insert_one(taskCollection)
                return {"error": err.args}
            if KeyError:

                logging.error(err)
                
                taskCollection = {"task_name": operationId,
                                    "start_time": dt_string,
                                    "organization": organization,
                                    "usefulParameter": usefulParameter,
                                    "category": category,
                                    "method": data.RollbackParameterTemplate["method"],
                                    "rollback": True,
                                    "parameter": parameter,

                                    "response": err,
                                    "rollback_response": Rollback_BackResponse,
                                    "error": True
                                    }
                task = await task_collection.insert_one(taskCollection)
                return {"error": err}
            else:
                logging.error(err.status)
                logging.error(err.reason)
                logging.error(err.message)
                
                taskCollection = {"task_name": operationId,
                                    "start_time": dt_string,
                                    "organization": organization,
                                    "usefulParameter": usefulParameter,
                                    "category": category,
                                    "method": data.RollbackParameterTemplate["method"],
                                    "rollback": True,
                                    "parameter": parameter,

                                    "response": err.reason,
                                    "rollback_response": Rollback_BackResponse,
                                    "error": True
                                    }
                task = await task_collection.insert_one(taskCollection)

            
            return {'status': err.status, "message": err.message, "error": err.reason}
        try:
            logging.info(f"{dt_string} NEW API CALL")
            API_KEY = data.RollbackParameterTemplate["apiKey"]
            dashboard = meraki.DashboardAPI(
                API_KEY, output_log=False, suppress_logging=False)
            category = data.RollbackParameterTemplate["category"]
            operationId = data.RollbackParameterTemplate["operationId"]
            parameter = data.RollbackParameterTemplate["parameter"]
            usefulParameter = data.RollbackParameterTemplate["usefulParameter"]

            loop_parameter = []
            rollBackLoopResponse = []
            for index, item in enumerate(parameter):
                # remove null/None parameter if any
                for key, value in item.copy().items():
                    if value == None:
                        item.pop(key)

                result = getattr(getattr(dashboard, category),
                                    operationId)(**item)
                rollBackLoopResponse.append(result)
                if usefulParameter == "networkId":
                    loop_parameter.append({"networkId": networkId, **item})
                elif usefulParameter == "serial":
                    loop_parameter.append({"serial": serial, **item})
                elif usefulParameter == "organizationId":
                    loop_parameter.append(
                        {"organizationId": organizationId, **item})
                logging.info(rollBackLoopResponse)
                
            taskCollection = {
                "task_name": operationId,
                "start_time": dt_string,
                "organization": organization,
                "usefulParameter": usefulParameter,
                "category": category,
                "method": data.RollbackParameterTemplate["method"],
                "rollback": True,
                "parameter": loop_parameter,

                "response": rollBackLoopResponse,
                "rollback_response": Rollback_BackResponse,
                "error": False
            }
            task = await task_collection.insert_one(taskCollection)
            return rollBackLoopResponse
        except (meraki.APIError, TypeError, KeyError) as err:
            if TypeError:
                logging.error(err.args)
                
                taskCollection = {
                    "task_name": operationId,
                    "start_time": dt_string,
                    "organization": organization,
                    "usefulParameter": usefulParameter,
                    "category": category,
                    "method": data.RollbackParameterTemplate["method"],
                    "rollback": True,
                    "parameter": loop_parameter,

                    "response": err.args,
                    "rollback_response": Rollback_BackResponse,
                    "error": True
                }
                task = await task_collection.insert_one(taskCollection)
                return {"error": err.args}
            if KeyError:
                logging.error(err)
                
                taskCollection = {
                    "task_name": operationId,
                    "start_time": dt_string,
                    "organization": organization,
                    "usefulParameter": usefulParameter,
                    "category": category,
                    "method": data.RollbackParameterTemplate["method"],
                    "rollback": True,
                    "parameter": loop_parameter,

                    "response": err,
                    "rollback_response": Rollback_BackResponse,
                    "error": True
                }
                task = await task_collection.insert_one(taskCollection)
                return {"error": err}
            else:
                logging.error(err.status)
                logging.error(err.reason)
                logging.error(err.message)
                taskCollection = {
                    "task_name": operationId,
                    "start_time": dt_string,
                    "organization": organization,
                    "usefulParameter": usefulParameter,
                    "category": category,
                    "method": data.RollbackParameterTemplate["method"],
                    "rollback": True,
                    "parameter": loop_parameter,

                    "response": err.reason,
                    "rollback_response": Rollback_BackResponse,
                    "error": True
                }
                task = await task_collection.insert_one(taskCollection)
                

            
            return {'status': err.status, "message": err.message, "error": err.reason}

    else:
        try:
            logging.info(f"{dt_string} NEW API CALL")
            API_KEY = data.RollbackParameterTemplate["apiKey"]
            dashboard = meraki.DashboardAPI(
                API_KEY, output_log=False, suppress_logging=False)
            category = data.RollbackParameterTemplate["category"]
            operationId = data.RollbackParameterTemplate["operationId"]
            rollbackId = operationId.replace("update", "get")
            parameter = data.RollbackParameterTemplate["parameter"]
            usefulParameter = data.RollbackParameterTemplate["usefulParameter"]
            RollbackResponse = {}

            if usefulParameter == "networkId":
                networkId = parameter["networkId"]
                RollbackResponse = getattr(
                    getattr(dashboard, category), rollbackId)(networkId)
                RollbackResponse["networkId"] = networkId
            elif usefulParameter == "serial":
                serial = parameter["serial"]
                RollbackResponse = getattr(
                    getattr(dashboard, category), rollbackId)(serial)
                RollbackResponse["serial"] = serial
            elif usefulParameter == "organizationId":
                organizationId = parameter["organizationId"]
                RollbackResponse = getattr(
                    getattr(dashboard, category), rollbackId)(organizationId)
                RollbackResponse["organizationId"] = organizationId
            else:
                RollbackResponse = getattr(
                    getattr(dashboard, category), rollbackId)(**parameter)

            logging.info(RollbackResponse)
            
        except (meraki.APIError, TypeError, KeyError) as err:
            if TypeError:

                logging.error(err.args)
                
                taskCollection = {"task_name": operationId,
                                    "start_time": dt_string,
                                    "organization": organization,
                                    "usefulParameter": usefulParameter,
                                    "category": category,
                                    "method": data.RollbackParameterTemplate["method"],
                                    "rollback": True,
                                    "parameter": parameter,

                                    "response": err.args,
                                    "rollback_response": RollbackResponse,
                                    "error": True
                                    }
                task = await task_collection.insert_one(taskCollection)
                return {"error": err.args}
            if KeyError:

                logging.error(err)
                
                taskCollection = {"task_name": operationId,
                                    "start_time": dt_string,
                                    "organization": organization,
                                    "usefulParameter": usefulParameter,
                                    "category": category,
                                    "method": data.RollbackParameterTemplate["method"],
                                    "rollback": True,
                                    "parameter": parameter,

                                    "response": err,
                                    "rollback_response": RollbackResponse,
                                    "error": True
                                    }
                task = await task_collection.insert_one(taskCollection)
                return {"error": err}
            else:
                logging.error(err.status)
                logging.error(err.reason)
                logging.error(err.message)
                
                taskCollection = {"task_name": operationId,
                                    "start_time": dt_string,
                                    "organization": organization,
                                    "usefulParameter": usefulParameter,
                                    "category": category,
                                    "method": data.RollbackParameterTemplate["method"],
                                    "rollback": True,
                                    "parameter": parameter,

                                    "response": err.reason,
                                    "rollback_response": RollbackResponse,
                                    "error": True
                                    }
                task = await task_collection.insert_one(taskCollection)

            
            return {'status': err.status, "message": err.message, "error": err.reason}

        try:
            logging.info(f"{dt_string} NEW API CALL")
            API_KEY = data.RollbackParameterTemplate["apiKey"]
            dashboard = meraki.DashboardAPI(
                API_KEY, output_log=False, suppress_logging=False)
            category = data.RollbackParameterTemplate["category"]
            operationId = data.RollbackParameterTemplate["operationId"]
            parameter = data.RollbackParameterTemplate["parameter"]
            # remove null/None parameter if any
            for key, value in parameter.copy().items():
                if value == None:
                    parameter.pop(key)

            result = getattr(getattr(dashboard, category),
                                operationId)(**parameter)
            logging.info(result)
            
            taskCollection = {
                "task_name": operationId,
                "start_time": dt_string,
                "organization": organization,
                "usefulParameter": usefulParameter,
                "category": category,
                "method": data.RollbackParameterTemplate["method"],
                "rollback": True,
                "parameter": parameter,

                "response": result,
                "rollback_response": RollbackResponse,
                "error": False
            }
            task = await task_collection.insert_one(taskCollection)
            return result
        except (meraki.APIError, TypeError, KeyError) as err:
            if TypeError:
                logging.error(err.args)
                
                taskCollection = {
                    "task_name": operationId,
                    "start_time": dt_string,
                    "organization": organization,
                    "usefulParameter": usefulParameter,
                    "category": category,
                    "method": data.RollbackParameterTemplate["method"],
                    "rollback": True,
                    "parameter": parameter,

                    "response": err.args,
                    "rollback_response": RollbackResponse,
                    "error": True
                }
                task = await task_collection.insert_one(taskCollection)
                return {"error": err.args}
            if KeyError:
                logging.error(err)
                
                taskCollection = {
                    "task_name": operationId,
                    "start_time": dt_string,
                    "organization": organization,
                    "usefulParameter": usefulParameter,
                    "category": category,
                    "method": data.RollbackParameterTemplate["method"],
                    "rollback": True,
                    "parameter": parameter,

                    "response": err,
                    "rollback_response": RollbackResponse,
                    "error": True
                }
                task = await task_collection.insert_one(taskCollection)
                return {"error": err}
            else:
                logging.error(err.status)
                logging.error(err.reason)
                logging.error(err.message)
                taskCollection = {
                    "task_name": operationId,
                    "start_time": dt_string,
                    "organization": organization,
                    "usefulParameter": usefulParameter,
                    "category": category,
                    "method": data.RollbackParameterTemplate["method"],
                    "rollback": True,
                    "parameter": parameter,

                    "response": err.reason,
                    "rollback_response": RollbackResponse,
                    "error": True
                }
                task = await task_collection.insert_one(taskCollection)
                

            
            return {'status': err.status, "message": err.message, "error": err.reason}
