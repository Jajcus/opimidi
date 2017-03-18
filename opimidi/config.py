import configparser
from collections import OrderedDict

class ConfigBank:
    def __init__(self, name, settings=None):
        self.name = name
        self.programs = OrderedDict()
        if settings:
            self.settings = settings
        else:
            self.settings = {}

class ConfigProgram:
    def __init__(self, bank, name, settings=None):
        self.bank = bank
        self.name = name
        if settings:
            self.settings = settings
        else:
            self.settings = {}

class Config:
    def __init__(self):
        self.config = configparser.ConfigParser(
                interpolation=configparser.ExtendedInterpolation())
        self.config.read("opimidi.config")
        self.banks = OrderedDict()
        for section in self.config:
            if ":" in section:
                bank_n, program_n = section.split(":", 1)
                if bank_n in self.banks:
                    bank = self.banks[bank_n]
                else:
                    bank = ConfigBank(bank_n)
                    self.banks[bank_n] = bank
                if program_n:
                    program = ConfigProgram(bank, program_n,
                                            self.config[section])
                    bank.programs[program_n] = program
                else:
                    bank.settings = self.config[section]
    def get_banks(self):
        return list(self.banks.values())

