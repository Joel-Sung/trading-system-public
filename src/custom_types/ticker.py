from enum import StrEnum


class Ticker(StrEnum):
    # =========================
    # Broad Market / Index
    # =========================
    SPY = "SPY"

    # =========================
    # Financials — XLF / KBE
    # Banks, insurers, asset managers
    # =========================
    XLF = "XLF"
    # BRK_B = "BRK-B" # Symbol for Tiingo
    BRK_B = "BRK.B"  # Symbol for Tiger
    JPM = "JPM"
    V = "V"
    MA = "MA"
    BAC = "BAC"
    WFC = "WFC"
    GS = "GS"
    MS = "MS"
    SPGI = "SPGI"
    BLK = "BLK"

    # =========================
    # Consumer Discretionary — XLY
    # Retail, autos, travel, luxury
    # =========================
    XLY = "XLY"
    AMZN = "AMZN"
    TSLA = "TSLA"
    HD = "HD"
    MCD = "MCD"
    NKE = "NKE"
    SBUX = "SBUX"
    LOW = "LOW"
    BKNG = "BKNG"
    TJX = "TJX"
    F = "F"

    # =========================
    # Industrials — XLI / IYT
    # Manufacturing, aerospace, logistics
    # =========================
    XLI = "XLI"
    GE = "GE"
    HON = "HON"
    CAT = "CAT"
    RTX = "RTX"
    BA = "BA"
    DE = "DE"
    LMT = "LMT"
    MMM = "MMM"
    ETN = "ETN"
    ITW = "ITW"

    # =========================
    # Transportation — IYT
    # =========================
    IYT = "IYT"
    UPS = "UPS"
    FDX = "FDX"
    UNP = "UNP"
    CSX = "CSX"
    NSC = "NSC"
    DAL = "DAL"
    LUV = "LUV"
    UBER = "UBER"
    ODFL = "ODFL"
    JBHT = "JBHT"

    # =========================
    # Semiconductors — SOXX
    # Hardware
    # =========================
    SOXX = "SOXX"
    AVGO = "AVGO"
    NVDA = "NVDA"
    MU = "MU"
    AMD = "AMD"
    MRVL = "MRVL"
    AMAT = "AMAT"
    INTC = "INTC"
    MPWR = "MPWR"
    KLAC = "KLAC"
    TER = "TER"

    # =========================
    # Technology — XLK
    # Software, semis
    # =========================
    XLK = "XLK"
    AAPL = "AAPL"
    MSFT = "MSFT"
    ADBE = "ADBE"
    CRM = "CRM"
    CSCO = "CSCO"
    ORCL = "ORCL"
    ACN = "ACN"
    IBM = "IBM"
    NOW = "NOW"
    TXN = "TXN"

    # =========================
    # Communication Services — XLC
    # Internet, media, telecom
    # =========================
    XLC = "XLC"
    GOOGL = "GOOGL"
    META = "META"
    NFLX = "NFLX"
    CMCSA = "CMCSA"
    DIS = "DIS"
    T = "T"
    VZ = "VZ"
    TMUS = "TMUS"
    CHTR = "CHTR"
    EA = "EA"

    # =========================
    # Energy — XLE / XOP
    # Oil, gas, energy services
    # =========================
    XLE = "XLE"
    XOM = "XOM"
    CVX = "CVX"
    COP = "COP"
    EOG = "EOG"
    SLB = "SLB"
    MPC = "MPC"
    VLO = "VLO"
    PSX = "PSX"
    KMI = "KMI"
    OXY = "OXY"

    # =========================
    # Materials — XLB / XME
    # Metals, chemicals, mining
    # =========================
    XLB = "XLB"
    XME = "XME"
    FCX = "FCX"
    NEM = "NEM"
    LIN = "LIN"
    SHW = "SHW"
    APD = "APD"
    ECL = "ECL"
    DOW = "DOW"
    DD = "DD"
    NUE = "NUE"
    PPG = "PPG"

    # =========================
    # Consumer Staples — XLP
    # Defensive consumer goods
    # =========================
    XLP = "XLP"
    PG = "PG"
    KO = "KO"
    PEP = "PEP"
    WMT = "WMT"
    COST = "COST"
    PM = "PM"
    MDLZ = "MDLZ"
    CL = "CL"
    KMB = "KMB"
    EL = "EL"

    # =========================
    # Healthcare — XLV
    # Pharma, biotech, insurance, devices
    # =========================
    XLV = "XLV"
    UNH = "UNH"
    LLY = "LLY"
    JNJ = "JNJ"
    MRK = "MRK"
    ABBV = "ABBV"
    PFE = "PFE"
    TMO = "TMO"
    ABT = "ABT"
    DHR = "DHR"
    BMY = "BMY"

    # =========================
    # Real Estate — XLRE
    # REITs (data centers, logistics, housing, retail)
    # =========================
    XLRE = "XLRE"
    PLD = "PLD"
    AMT = "AMT"
    EQIX = "EQIX"
    PSA = "PSA"
    O = "O"
    SPG = "SPG"
    DLR = "DLR"
    WELL = "WELL"
    AVB = "AVB"
    EQR = "EQR"

    # =========================
    # Utilities — XLU
    # Regulated power & energy utilities
    # =========================
    XLU = "XLU"
    NEE = "NEE"
    DUK = "DUK"
    SO = "SO"
    D = "D"
    AEP = "AEP"
    EXC = "EXC"
    SRE = "SRE"
    XEL = "XEL"
    PEG = "PEG"
    EIX = "EIX"

    # =========================
    # Bonds / Rates
    # Fixed income exposure (duration / inflation)
    # =========================
    TLT = "TLT"
    IEF = "IEF"
    SHY = "SHY"
    TIP = "TIP"

    # =========================
    # FX / Currency ETFs
    # =========================
    UUP = "UUP"
    FXE = "FXE"
    FXY = "FXY"
    FXA = "FXA"
    FXB = "FXB"
    FXF = "FXF"
