# README #

### How do I get set up? ###

* Summary of set up
  * usage/help information
  
        usage: appsdeploy.py [-h] -u JENKURL -b BRANCH -e ENV [--i] -l LOGLEVEL -s
                             SVNURL [-r] -j JIRATICKET
                             [planfile]

        positional arguments:
          planfile              .plan file that is the deployment program

        optional arguments:
          -h, --help            show this help message and exit
          -u JENKURL, --jenkurl JENKURL
                                jenkins url for the artifact (mandatory)
          -b BRANCH, --branch BRANCH
                                svn branch number (mandatory)
          -e ENV, --env ENV     execution environment (mandatory)
          --i                   start interactive repl
          -l LOGLEVEL, --loglevel LOGLEVEL
                                logging level
          -s SVNURL, --svnurl SVNURL
                                svn url for repository
          -r, --relativebackup  use relative path for backing up files
          -j JIRATICKET, --jiraticket JIRATICKET
                                jira ticket number for deployment


* Dependencies
  * python version 2.7
* Deployment instructions
  * download appsdeploy.py
  * run it like above

### Contribution guidelines ###

* to be updated

### Who do I talk to? ###

* hmahapatro
