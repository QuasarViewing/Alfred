from gmail_tool import get_unread_emails, search_emails, send_email, create_draft

# Test search                                                                                                           
print(search_emails("from:google.com"))


# Test draft (safe - doesn't send)
print(create_draft("youremail@gmail.com", "Test Draft", "This is a test draft from Alfred."))

