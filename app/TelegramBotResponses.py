import logging
import json
from random import choice

logger = logging.getLogger(__name__)

class TelegramBotResponses:
    """
    Class that provides an interface to bot response file - file that stores list of bot responses
    """
    def __init__(self, filename):
        self.responses = self.get_responses(filename)

    def get_responses(self, responses_file):
        """
        Get bot responses defined in self.RESPONSES_FILE

        Returns:
            dict
        """
        try:
            with open(responses_file, 'r') as fp:
                responses = json.load(fp)
            return responses

        except FileNotFoundError:
            logger.info('Responses file {} not found. Exiting'.format(responses_file))
            exit()

    def get_random_response(self, state):
        """
        Return random response from config_file

        Returns:
            string
        """
        try:
            assert state in self.responses.keys()  # should be called only with states defined in self.RESPONSES_FILE
        except AssertionError:
            logger.info('No response found for ' + state)
            logger.info(self.responses.keys())
            exit()

        response = choice(self.responses[state])
        return response

    def get_one_response(self, state):
        """
        Return response from config_file when there is only one possible

        Returns:
            string

        """
        try:
            assert state in self.responses.keys()  # should be called only with states defined in self.RESPONSES_FILE
        except AssertionError:
            logger.info('No response found for ' + state)
            logger.info(self.responses.keys())
            exit()

        response = self.responses[state][0]
        return response