class CLR:
    use_color = True
    conky = False

    def __str__(self):
        return self.color if self.use_color else ''


class CLR_NRM(CLR):
    color = "\033[0m"


class CLR_BLK(CLR):
    color = "\033[0;30m"


class CLR_BRBLK(CLR):
    color = "\033[30;1m"


class CLR_RED(CLR):
    color = "\033[0;31m"


class CLR_BRRED(CLR):
    color = "\033[31;1m"


class CLR_GRN(CLR):
    color = "\033[0;32m"


class CLR_BRGRN(CLR):
    color = "\033[32;1m"


class CLR_YLW(CLR):
    color = "\033[0;33m"


class CLR_BRYLW(CLR):
    color = "\033[33;1m"


class CLR_BLU(CLR):
    color = "\033[0;34m"


class CLR_BRBLU(CLR):
    color = "\033[34;1m"


class CLR_MAG(CLR):
    color = "\033[0;35m"


class CLR_BRMAG(CLR):
    color = "\033[35;1m"


class CLR_CYN(CLR):
    color = "\033[0;36m"


class CLR_BRCYN(CLR):
    color = "\033[36;1m"


class CLR_WHT(CLR):
    color = "\033[0;37m"


class CLR_BRWHT(CLR):
    color = "\033[37;1m"


def SetConkyColors():
    # XXX these colors should be configurable
    CLR.conky = True
    CLR_NRM.color = ""
    CLR_BLK.color = "${color black}"
    CLR_BRBLK.color = "${color black}"
    CLR_RED.color = "${color red}"
    CLR_BRRED.color = "${color red}"
    CLR_GRN.color = "${color green}"
    CLR_BRGRN.color = "${color green}"
    CLR_YLW.color = "${color yellow}"
    CLR_BRYLW.color = "${color yellow}"
    CLR_BLU.color = "${color blue}"
    CLR_BRBLU.color = "${color blue}"
    CLR_MAG.color = "${color magenta}"
    CLR_BRMAG.color = "${color magenta}"
    CLR_CYN.color = "${color cyan}"
    CLR_BRCYN.color = "${color cyan}"
    CLR_WHT.color = "${color white}"
    CLR_BRWHT.color = "${color white}"
