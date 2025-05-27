from dataclasses import dataclass
from typing import List, Optional
from datetime import datetime
import re

@dataclass
class AmountCondition:
    """金额条件"""
    Flag: int
    Lower: float
    Upper: float

    @classmethod
    def from_dict(cls, data: dict) -> 'AmountCondition':
        """从字典创建实例"""
        return cls(
            Flag=int(data.get('Flag', 0)),
            Lower=float(data.get('Lower', 0)),
            Upper=float(data.get('Upper', 0))
        )

@dataclass
class PayModeInfo:
    """支付模式信息"""
    TradeFlow: str
    TradeFlow_DTBank: bool
    AmountCondition: AmountCondition

    @classmethod
    def from_dict(cls, data: dict) -> 'PayModeInfo':
        """从字典创建实例"""
        return cls(
            TradeFlow=str(data.get('TradeFlow', '')),
            TradeFlow_DTBank=bool(data.get('TradeFlow_DTBank', False)),
            AmountCondition=AmountCondition.from_dict(data.get('AmountCondition', {}))
        )

@dataclass
class BankCard:
    """银行卡信息"""
    # PayPlusDesc: Optional[str]
    # IsPayPlus: bool
    PayPlusFundCode: Optional[str]
    PayPlusFundName: Optional[str]
    ShowPayPlusFundCode: bool
    AccountNo: str
    BankCode: str
    ShowBankCode: str
    BankName: str
    BankCardNo: str
    BankCardType: str
    BankState: bool
    AccountState: int
    OpenTime: Optional[str]
    CreateTime: Optional[str]
    HasBranch: bool
    CanPayment: bool
    Limitation: Optional[float]
    EnableTips: bool
    Tips: str
    EnableChannelTips: bool
    ChannelTips: Optional[str]
    ChannelTipsType: int
    Title: str
    FontColor: str
    BgColor: str
    FastAvaVol: Optional[str]
    SupportRemittance: bool
    PayModeInfos: List[PayModeInfo]
    SuggestChannelForBank: str
    OpenTradeChannels: List[str]

    @classmethod
    def from_dict(cls, data: dict) -> 'BankCard':
        """从字典创建实例"""
        pay_mode_infos = [
            PayModeInfo.from_dict(info) for info in data.get('PayModeInfos', [])
        ]
        
        # 处理日期格式
        create_time = cls._parse_date(data.get('CreateTime', ''))
        open_time = data.get('OpenTime', '')
        
        return cls(
            # PayPlusDesc=data.get('PayPlusDesc'),
            # IsPayPlus=bool(data.get('IsPayPlus', False)),
            PayPlusFundCode=data.get('PayPlusFundCode'),
            PayPlusFundName=data.get('PayPlusFundName'),
            ShowPayPlusFundCode=bool(data.get('ShowPayPlusFundCode', False)),
            AccountNo=str(data.get('AccountNo', '')),
            BankCode=str(data.get('BankCode', '')),
            ShowBankCode=str(data.get('ShowBankCode', '')),
            BankName=str(data.get('BankName', '')),
            BankCardNo=str(data.get('BankCardNo', '')),
            BankCardType=str(data.get('BankCardType', '')),
            BankState=bool(data.get('BankState', True)),
            AccountState=int(data.get('AccountState', 0)),
            OpenTime=open_time,
            CreateTime=create_time,
            HasBranch=bool(data.get('HasBranch', True)),
            CanPayment=bool(data.get('CanPayment', True)),
            Limitation=float(data.get('Limitation', 0)) if data.get('Limitation') is not None else None,
            EnableTips=bool(data.get('EnableTips', True)),
            Tips=str(data.get('Tips', '')),
            EnableChannelTips=bool(data.get('EnableChannelTips', False)),
            ChannelTips=data.get('ChannelTips'),
            ChannelTipsType=int(data.get('ChannelTipsType', 0)),
            Title=str(data.get('Title', '')),
            FontColor=str(data.get('FontColor', '#FFFFFF')),
            BgColor=str(data.get('BgColor', '#FF6434')),
            FastAvaVol=data.get('FastAvaVol'),
            SupportRemittance=bool(data.get('SupportRemittance', True)),
            PayModeInfos=pay_mode_infos,
            SuggestChannelForBank=str(data.get('SuggestChannelForBank', '')),
            OpenTradeChannels=list(data.get('OpenTradeChannels', []))
        )

    @staticmethod
    def _parse_date(date_str: str) -> Optional[str]:
        """解析日期字符串"""
        if not date_str:
            return None
            
        # 处理 /Date(timestamp)/ 格式
        timestamp_match = re.match(r'/Date\((\d+)\)/', date_str)
        if timestamp_match:
            timestamp = int(timestamp_match.group(1)) / 1000  # 转换为秒
            return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
            
        return date_str

@dataclass
class HqbBank:
    """活期宝银行卡信息"""
    AccountNo: str
    BankCardNo: str
    BankCode: str
    BankName: str
    BankType: str
    BankState: bool
    BankAvaVol: str
    CurrentRealBalance: float
    HasBranch: bool
    ShowBankCode: str
    BankCardType: str
    AccountState: int
    CanPayment: bool
    EnableTips: bool
    Tips: Optional[str]
    EnableChannelTips: bool
    ChannelTips: Optional[str]
    RechargeTitle: Optional[str]
    Title: Optional[str]
    OpenTime: Optional[str]
    CreateTime: Optional[str]

    @classmethod
    def from_dict(cls, data: dict):
        """从字典创建HqbBank对象"""
        return cls(
            AccountNo=data.get('AccountNo', ''),
            BankCardNo=data.get('BankCardNo', ''),
            BankCode=data.get('BankCode', ''),
            BankName=data.get('BankName', ''),
            BankType=data.get('BankType', ''),
            BankState=data.get('BankState', False),
            BankAvaVol=data.get('BankAvaVol', '0.00'),
            CurrentRealBalance=float(data.get('CurrentRealBalance', 0.0)),
            HasBranch=data.get('HasBranch', False),
            ShowBankCode=data.get('ShowBankCode', ''),
            BankCardType=data.get('BankCardType', ''),
            AccountState=data.get('AccountState', 0),
            CanPayment=data.get('CanPayment', True),
            EnableTips=data.get('EnableTips', False),
            Tips=data.get('Tips'),
            EnableChannelTips=data.get('EnableChannelTips', False),
            ChannelTips=data.get('ChannelTips'),
            RechargeTitle=data.get('RechargeTitle'),
            Title=data.get('Title'),
            OpenTime=data.get('OpenTime'),
            CreateTime=data.get('CreateTime')
        )

    @staticmethod
    def _parse_date(date_str: str) -> Optional[str]:
        """解析日期字符串"""
        if not date_str:
            return None
            
        # 处理 /Date(timestamp)/ 格式
        timestamp_match = re.match(r'/Date\((\d+)\)/', date_str)
        if timestamp_match:
            timestamp = int(timestamp_match.group(1)) / 1000  # 转换为秒
            return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
            
        return date_str

@dataclass
class BankResponse:
    """银行卡信息响应"""
    Banks: List[BankCard]
    IntellMinVol: str
    IntellMaxVol: str
    ProfitDate: str
    RecommendHqbTips: str
    HqbProfitTip: str
    Succeed: str
    Scode: int
    Desc: str
    Time: str
    HqbThirdAndZhVols: Optional[str]
    UnavailableHqbBanks: List[str]
    HqbBanks: List[HqbBank]
    MinKeepForFast: float
    HqbPayText: str
    HqbPayNotUsedText: str
    HqbThirdAndZhVolTitle: Optional[str]
    HqbPayDiscountText: str
    BankCacdPayDiscountText: str
    ZhbText: Optional[str]

@dataclass
class BankApiResponse:
    """银行卡API响应"""
    Data: BankResponse
    IsDowngrade: bool
    ErrorCode: int
    InnerErrorCode: Optional[str]
    ErrorMessage: List[str]
    FirstError: Optional[str]
    Message: Optional[str]
    DebugError: Optional[str]
    Success: bool
    NotCache: bool
    UserMigration: Optional[str]
    HasWrongToken: bool

    @classmethod
    def from_dict(cls, data: dict) -> 'BankApiResponse':
        """从字典创建实例"""
        response_data = data.get('Data', {})
        bank_response = BankResponse.from_dict(response_data)
        
        return cls(
            Data=bank_response,
            IsDowngrade=bool(data.get('IsDowngrade', False)),
            ErrorCode=int(data.get('ErrorCode', 0)),
            InnerErrorCode=data.get('InnerErrorCode'),
            ErrorMessage=list(data.get('ErrorMessage', [])),
            FirstError=data.get('FirstError'),
            Message=data.get('Message'),
            DebugError=data.get('DebugError'),
            Success=bool(data.get('Success', False)),
            NotCache=bool(data.get('NotCache', False)),
            UserMigration=data.get('UserMigration'),
            HasWrongToken=bool(data.get('HasWrongToken', False))
        )