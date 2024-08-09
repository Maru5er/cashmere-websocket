import os
import sys
from typing import List
from typing_extensions import override
from openai import AssistantEventHandler, OpenAI
import dotenv


class Cashmere:
  def __init__(self, file=None) -> None:
    dotenv.load_dotenv()
    self.client = OpenAI()

    # intialize assistant
    self.assistant = self.client.beta.assistants.retrieve(
       assistant_id="asst_bqZYJzrKKRYBtTY0XUmg6hFZ"
    )
    """
    self.assistant = self.client.beta.assistants.create(
      name="Medical Nurse Assistant with tool choice",
      instructions="You are an expert nurse. Use the knowledge base to ask about patient's progress and well-being and help answer doctor's questions about the patient and recommend tests. It is important that you ask for more information about the patient from the question bank if you don't already have that information. Always address the patient by their name",
      model="gpt-4o",
      tools=[{"type" : "file_search"}],
    )
    """
    

    # vectorize question bank
    vector_store = self.client.beta.vector_stores.create(name="Question Bank")
    file_paths = ["sample_data/questions.txt"]
    file_streams = [open(path, "rb") for path in file_paths]
    file_batch = self.client.beta.vector_stores.file_batches.upload_and_poll(
      vector_store_id=vector_store.id, files=file_streams
    )
    self.client.beta.assistants.update(
      assistant_id=self.assistant.id,
      tool_resources={"file_search": {"vector_store_ids": [vector_store.id]}},
    )

    self.file_uploaded = False

    
    # initialize a thread
    if file:
      self.file_uploaded = True
      # User uploads the document
      try:
        message_file = self.client.files.create(
          file=open(file, "rb"), purpose="assistants"
        )
        self.thread = self.client.beta.threads.create(
          messages=[
            {
              "role": "user",
              "content": "use this uploaded document to help you retrieve information necessary to populate the question bank. Ask me for more information that you cannot find from this document",
              # Attach the new file to the message.
              "attachments": [
                { "file_id": message_file.id, "tools": [{"type": "file_search"}] }
              ],
            }
          ]
        )
      except:
        print("File cannot be read")
        # TODO: need to change what to do when file error
        sys.exit()
        
    else:
      # no document uploaded
      self.thread = self.client.beta.threads.create(
          messages=[
            {
              "role": "user",
              "content": "Please ask me the questions from the question bank",
            }
          ]
        )
  
  def add_message(self, message: str, role: str ="user" ):
    """add messages to the thread of current instance
    
    Args:
      message: the message

    Returns:
      None
    """
    self.client.beta.threads.messages.create(
      role=role,
      thread_id=self.thread.id,
      content=message,
    )

  def retrieve_messages(self):
    """Retrieves message history of current thread instance
    
    Args:
      None

    Returns:
      Array of Messages data
    """
    return self.client.beta.threads.messages.list(self.thread.id).data
  
  def process(self):
    """Process current chat with stream. prints out response

    Args:
    None

    Returns:
    None

    """
    if self.file_uploaded:
      instruction = """The patient has uploaded their medical record. 
                  You are tasked to ask the patient more information.
                  Only ask questions related to the question bank. 
                  Please address the patient by their name and asks a maximum of 3 questions at a time
                  """
    else:
      instruction = """
            You are tasked to ask the patient more information.
            Only ask questions related to the question bank.
            Please address the patient by their name and asks a maximum of 3 questions at a time
          """

    event_handler=EventHandler(self.client)
    with self.client.beta.threads.runs.stream(
        thread_id=self.thread.id,
        assistant_id=self.assistant.id,
        instructions=instruction,
        event_handler=event_handler,
        tool_choice={"type": "file_search"}
    ) as stream:
        stream.until_done()
        result = ''.join(event_handler.accumulated_text)

    return result

  def end_conversation(self):
     """Ends current conversation and generate a new report
     
     Args:
      None

    Returns:
      None

     """
     self.add_message("Please generate a new report based on our interaction so far")
     self.process()

# Event Handler class for assistant 
class EventHandler(AssistantEventHandler):
    def __init__(self, client):
      super().__init__()
      self.client = client
      self.accumulated_text = []

    @override
    def on_text_created(self, text) -> None:
        print(f"\nassistant > ", end="", flush=True)

    @override
    def on_tool_call_created(self, tool_call):
        print(f"\nassistant > {tool_call.type}\n", flush=True)

    @override
    def on_message_done(self, message):
        # print a citation to the file searched
        message_content = message.content[0].text
        annotations = message_content.annotations

        self.accumulated_text.append(message_content.value)

