#
# $Source$
# $Date: 2008-05-04 23:01:22 -0500 (Sun, 04 May 2008) $
# $Revision: 328 $
#
# DESCRIPTION:
# Engine for scanning scorebooks to accumulate statistics
# 
# This file is part of Chadwick, a library for baseball play-by-play and stats
# Copyright (C) 2005-2007, Ted Turocy (drarbiter@gmail.com)
#
# This program is free software; you can redistribute it and/or modify 
# it under the terms of the GNU General Public License as published by 
# the Free Software Foundation; either version 2 of the License, or (at 
# your option) any later version.
#
# This program is distributed in the hope that it will be useful, but 
# WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY 
# or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License 
# for more details.
#
# You should have received a copy of the GNU General Public License along 
# with this program; if not, write to the Free Software Foundation, Inc., 
# 59 Temple Place, Suite 330, Boston, MA 02111-1307 USA
# 

import libchadwick as cw
import report
import report.statline
import report.team
import report.register

class BigGameLog:
    """
    This is a log report for 'big games' by players.  It provides
    the generic stuff needed to generate such a report.  Derived
    reports should provide three functions: the OnEvent() function;
    a GetHeader() function, which returns the text string placed over
    the count in the text output; and a GetThreshold() function to
    indicate the statistical count needed to appear in the report.
    """
    def __init__(self, book):
        self.events = [ ]
        self.book = book

    # Provide us in derived class!
    def GetTitle(self):   return ""
    def GetHeader(self):  return ""
    def GetThreshold(self):  return 2
    def IsOffense(self):  return True
    def OnEvent(self, game, gameiter):  pass
    
    def OnBeginGame(self, game, gameiter): self.counts = [ { }, { } ]
    def OnSubstitution(self, game, gameiter): pass

    def OnEndGame(self, game, gameiter):
        for (t,team) in enumerate(self.counts):
            for key in team:
                if team[key] >= self.GetThreshold():
                    if self.IsOffense():
                        self.events.append({ "game": game,
                                             "batter": key,
                                             "team": game.GetTeam(t),
                                             "opp": game.GetTeam(1-t),
                                             "site": game.GetTeam(1),
                                             "count": team[key] })
                    else:
                        self.events.append({ "game": game,
                                             "batter": key,
                                             "team": game.GetTeam(1-t),
                                             "opp": game.GetTeam(t),
                                             "site": game.GetTeam(1),
                                             "count": team[key] })


    def __str__(self):
        s = "\n%s\n" % self.GetTitle()
        s += ("\nPlayer                         Date           Team Opp  Site  %2s\n" %
             self.GetHeader())

        self.events.sort(lambda x, y:
                         cmp(x["game"].GetDate()+x["site"]+str(x["game"].GetNumber()),
                             y["game"].GetDate()+y["site"]+str(y["game"].GetNumber())))
        
        for rec in self.events:
            player = self.book.GetPlayer(rec["batter"])
            s += ("%-30s %10s %s %s  %s  %s   %2d\n" %
                  (player.GetSortName(),
                   rec["game"].GetDate(),
                   [ "   ", "(1)", "(2)" ][rec["game"].GetNumber()],
                   rec["team"], rec["opp"], rec["site"],
                   rec["count"]))

        return s


class MultiHRLog(BigGameLog):
    def __init__(self, book):  BigGameLog.__init__(self, book)

    def GetTitle(self):
        return ("Players with at least %d home runs in a game" %
                self.GetThreshold())
    def GetHeader(self):  return "HR"
    def GetThreshold(self):  return 2
    def IsOffense(self):  return True
    
    def OnEvent(self, game, gameiter):
        eventData = gameiter.GetEventData()
        team = gameiter.event.batting_team

        if eventData.event_type == cw.EVENT_HOMERUN:
            batter = gameiter.event.batter
            if gameiter.event.batter in self.counts[team]:
                self.counts[team][batter] += 1
            else:
                self.counts[team][batter] = 1

class MultiHitLog(BigGameLog):
    def __init__(self, book):  BigGameLog.__init__(self, book)

    def GetTitle(self):
        return ("Players with at least %d hits in a game" %
                self.GetThreshold())
    def GetHeader(self):  return "H"
    def GetThreshold(self):  return 4
    def IsOffense(self):  return True
    
    def OnEvent(self, game, gameiter):
        eventData = gameiter.GetEventData()
        team = gameiter.event.batting_team

        if eventData.event_type in [ cw.EVENT_SINGLE,
                                     cw.EVENT_DOUBLE,
                                     cw.EVENT_TRIPLE,
                                     cw.EVENT_HOMERUN ]:
            batter = gameiter.event.batter
            if gameiter.event.batter in self.counts[team]:
                self.counts[team][batter] += 1
            else:
                self.counts[team][batter] = 1

class MultiStrikeoutLog(BigGameLog):
    def __init__(self, book):  BigGameLog.__init__(self, book)

    def GetTitle(self):
        return ("Pitchers with at least %d strikeouts in a game" %
                self.GetThreshold())
    def GetHeader(self):  return "SO"
    def GetThreshold(self):  return 10
    def IsOffense(self):  return False
    
    def OnEvent(self, game, gameiter):
        eventData = gameiter.GetEventData()
        team = gameiter.event.batting_team

        if eventData.event_type == cw.EVENT_STRIKEOUT:
            pitcher = gameiter.GetFielder(1-team, 1)
            if pitcher in self.counts[team]:
                self.counts[team][pitcher] += 1
            else:
                self.counts[team][pitcher] = 1


def process_game(game, reports):
    gameiter = cw.GameIterator(game)
    for report in reports:  report.OnBeginGame(game, gameiter)

    while gameiter.event is not None:
        if gameiter.event.event_text != "NP":
            for report in reports:  report.OnEvent(game, gameiter)

        if gameiter.event.first_sub is not None:
            for report in reports:  report.OnSubstitution(game, gameiter)

        gameiter.NextEvent()

    for report in reports:  report.OnEndGame(game, gameiter)
 
def process_file(book, acclist, f=lambda x: True, monitor=None):
    """
    Process the games in scorebook 'book' through the list of
    accumulators in 'acclist'.  Instrumented so that if
    'monitor' is None, progress indications (via calls to
    monitor.Update) are given -- thus the wxWidgets wxProgressDialog
    automatically works for this parameter.
    """
    numGames = book.NumGames()
    for (i,game) in enumerate(book.Games()):
        if f(game):
            process_game(game, acclist)
            if monitor != None:
                if not monitor.Update(round(float(i)/float(numGames)*100)):
                    return False
    return True

def print_report(book, report):
    process_file(book, [ report ])
    print str(report)

if __name__ == "__main__":
    import sys
    import scorebook
    import dw

    book = dw.Reader(sys.argv[1])

    #x = [ PitchingRegister(book) ]
    #for team in book.Teams():
    #    x.append(TeamPitchingRegister(book, team.GetID()))
    #x = [ Standings(book),
    #      TeamBattingTotals(book),
    #      TeamPitchingTotals(book),
    #      TeamFieldingTotals(book) ]
    #x = [ MultiHRLog(book), MultiHitLog(book), MultiStrikeoutLog(book) ]
    #x = [ BattingDailies(book, "bondb001") ]


    print "CONTINENTAL BASEBALL LEAGUE OFFICIAL STATISTICS"
    print "COORDINATOR OF STATISTICAL SERVICES, THEODORE L. TUROCY, COLLEGE STATION TX -- (979) 997-0666 -- drarbiter@gmail.com"
    print

    print "COMPOSITE STANDING OF CLUBS THROUGH GAMES OF XXX"

    standings = report.team.Standings(book)
    process_file(book, [standings])
    print_report(book, report.team.Standings(book))


    print "TEAM BATTING"
    print_report(book, report.team.TeamBattingTotals(book))

    print "TEAM PITCHING"
    print_report(book, report.team.TeamPitchingTotals(book))

    print "TEAM FIELDING"
    print_report(book, report.team.TeamFieldingTotals(book))

    batting = report.register.Batting(book)
    process_file(book, [ batting ])

    print "LEADING BATTERS (MINIMUM 3.1 PLATE APPEARANCES PER TEAM GAME PLAYED)"
    subrep = batting.filter(lambda x: x.pa>=3.1*standings.stats[x.team.GetID()].g)
    subrep.sorter = lambda x,y: cmp(y.avg, x.avg)
    print str(subrep)

    print "ALL BATTERS, ALPHABETICALLY"
    print str(batting)

    #for team in book.Teams():
    #    subrep = rep.filter(lambda x: x.team is team)
    #    print str(subrep)

    pitching = report.register.Pitching(book)
    process_file(book, [ pitching ])

    print "LEADING PITCHERS (MINIMUM 1 INNING PITCHED PER TEAM GAME PLAYED)"

    subrep = pitching.filter(lambda x: x.outs>=3*standings.stats[x.team.GetID()].g)
    subrep.sorter = lambda x,y: cmp(x.era, y.era)
    print str(subrep)

    print "ALL PITCHERS, ALPHABETICALLY"
    print str(pitching)
    
    