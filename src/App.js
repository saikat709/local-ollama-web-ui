import React, { useState, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import { FiSend, FiXCircle, FiUser, FiCpu } from 'react-icons/fi';
import './App.css';

const Spinner = () => (
  <div className="loading-indicator">
    <div className="spinner"></div>
  </div>
);


const OlympiadInfo = () => {
  return (
    <div className="olympiad-info">
      <h2>Welcome to the Olympiad Preparation Chat!</h2>
      <p>
        This chat is designed to help you prepare for various Olympiads by providing information, resources, and practice questions.
      </p>
      <ul>
      <li><strong>Math Olympiad:</strong> Get tips on problem-solving techniques, past papers, and study materials.</li>
      <li><strong>Science Olympiad:</strong> Explore topics in physics, chemistry, and biology with curated resources.</li>
      <li><strong>Programming Olympiad:</strong> Practice coding problems and learn algorithms and data structures.</li>
    </ul>
    <p>Feel free to ask any questions or request specific resources to aid your preparation!</p>
  </div>
  );
};


function App() {
  const [prompt, setPrompt] = useState('');
  const [messages, setMessages] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const abortControllerRef = useRef(null);
  const chatContainerRef = useRef(null);

  const handleInputChange = (e) => {
    setPrompt(e.target.value);
  };

  const handleSend = async () => {
    if (!prompt.trim()) return;

    const newMessages = [...messages, { text: prompt, sender: 'user' }];
    setMessages(newMessages);
    setPrompt('');
    setIsLoading(true);

    abortControllerRef.current = new AbortController();

    // Load balancer ip: 10.100.201.91

    try {
      const response = await fetch('http://10.100.201.91:8000/stream', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          model: 'llama3.1',
          prompt: prompt,
          stream: true,
          seed: 42,
          num_predict: 10,
          mirostat: 0,
          temperature: 0.2,
          top_k: 0,
          top_p: 1.0,
          typical_p: 1.0,
          min_p: 0.0,
          repeat_last_n: 64,
          repeat_penalty: 1.05,
          presence_penalty: 0.0,
          frequency_penalty: 0.0,
          penalize_newline: false,
          stop: ['user:'],
          num_ctx: 10,
          num_keep: -1,
          numa: false,
          num_thread: 8,
          num_batch: 128,
          num_gpu: -1,
          main_gpu: 0,
          low_vram: false,
          use_mmap: true,
          use_mlock: false,
          vocab_only: false,
          options: {
            num_predict: 512,
          }
        }),
        signal: abortControllerRef.current.signal,
      });

      if (!response.body) return;

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let botMessage = '';

      setMessages(prevMessages => [...prevMessages, { text: '', sender: 'bot' }]);

      const processStream = async () => {
        while (true) {
          try {
            const { done, value } = await reader.read();
            if (done) {
              setIsLoading(false);
              break;
            }

            const chunk = decoder.decode(value, { stream: true });
            const jsonChunks = chunk.split('\n').filter(c => c);

            jsonChunks.forEach(jsonChunk => {
              const parsed = JSON.parse(jsonChunk);
              if (parsed.response) {
              console.log('Reading stream...');
                botMessage += parsed.response;
                setMessages(prevMessages => {
                  const newMessages = [...prevMessages];
                  newMessages[newMessages.length - 1] = {
                    ...newMessages[newMessages.length - 1],
                    text: botMessage,
                  };
                  return newMessages;
                });
              }
            });
          } catch (error) {
            console.error('Error parsing JSON chunk:', error);
            setIsLoading(false);
            break;
          }
        }
      };

      processStream();

    } catch (error) {
      if (error.name === 'AbortError') {
        console.log('Fetch aborted');
      } else {
        console.error('Error fetching data:', error);
      }
      setIsLoading(false);
    }
  };

  const handleCancel = () => {
    if ( abortControllerRef.current ) {
      if (!abortControllerRef.current.signal.aborted) {
        abortControllerRef.current.abort();
      }
    }
    console.log("AbortCController: ", abortControllerRef.current.signal.aborted);
    setIsLoading(false);
  };

  useEffect(() => {
    if (chatContainerRef.current) {
      chatContainerRef.current.scrollTop = chatContainerRef.current.scrollHeight;
    }
  }, [messages]);

  useEffect(() => {
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, []);

  return (
    <div className="App">
      <header className="header">
        <h1>Ollama Chat</h1>
      </header>

      {messages.length === 0 && !isLoading && <OlympiadInfo />}

      <div className="chat-container" ref={chatContainerRef}>
        {messages.map((msg, index) => (
          <div key={index} className={`chat-message ${msg.sender}-message`}>
            <div className={`avatar ${msg.sender === 'bot' && "bot"}`}>
              {msg.sender === 'user' ? <FiUser /> : <FiCpu />}
            </div>
            <div className="message-content">
              <ReactMarkdown>{msg.text}</ReactMarkdown>
            </div>
          </div>
        ))}
        {isLoading && <Spinner />}
      </div>
      <div className="input-area">
        <div className="input-container">
          <textarea
            value={prompt}
            // disabled={isLoading}
            onChange={handleInputChange}
            placeholder="Type your message here..."
            rows="1"
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleSend();
              }
            }}
          />
          <div className="button-container">
            <button onClick={handleSend} disabled={isLoading}>
              <FiSend />
            </button>
            { isLoading && (
              <button onClick={handleCancel} className="cancel-button">
                <FiXCircle />
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;